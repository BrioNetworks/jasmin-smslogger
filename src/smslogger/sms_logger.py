# -*- coding: utf-8 -*-
import pickle

import datetime
import txamqp.spec
import txamqp
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator

from txamqp.protocol import AMQClient
from txamqp.client import TwistedDelegate

from txamqp.queue import Closed

from smslogger import settings
from smslogger.sms_buffer import BufferManager
from smslogger.utils import get_multipart_message, decode_message, utc_to_local
from smslogger.app_logger import logger


class SmsLogger(object):

    def __init__(self):
        self.amqp_conn = settings.AMQP_CONNECTION
        self.spec = txamqp.spec.load(settings.AMQP_SPECIFICATION)
        self.buffer = BufferManager()

    def start(self):
        vhost = self.amqp_conn['vhost']
        host = self.amqp_conn['host']
        port = self.amqp_conn['port']

        d = ClientCreator(reactor,
                          AMQClient,
                          delegate=TwistedDelegate(),
                          vhost=vhost,
                          spec=self.spec).connectTCP(host, port)

        d.addCallback(self.got_connection)
        d.addErrback(self.whoops)

    def whoops(self, error):
        logger.error(error)
        if reactor.running:
            reactor.stop()

    @inlineCallbacks
    def got_connection(self, conn):
        logger.info('Connected to broker')

        username = self.amqp_conn['user']
        password = self.amqp_conn['password']
        yield conn.start({"LOGIN": username, "PASSWORD": password})

        logger.info('Authenticated. Ready to receive messages')
        chan = yield conn.channel(1)
        yield chan.channel_open()

        queue_name = 'sms_logger_queue'
        queue_tag = 'sms_logger'

        yield chan.queue_declare(queue=queue_name)

        # Привязка к submit.sm.*, submit.sm.resp.*, dlr_thrower.* маршрутам
        yield chan.queue_bind(queue=queue_name, exchange='messaging', routing_key='submit.sm.*')
        yield chan.queue_bind(queue=queue_name, exchange='messaging', routing_key='submit.sm.resp.*')
        yield chan.queue_bind(queue=queue_name, exchange='messaging', routing_key='dlr_thrower.*')

        yield chan.basic_consume(queue=queue_name, no_ack=False, consumer_tag=queue_tag)
        queue = yield conn.queue(queue_tag)

        # Ожидаем сообщения
        while True:
            try:
                msg = yield queue.get()
            except Closed:
                logger.info('Connection is closed!')
                break

            props = msg.content.properties

            if msg.routing_key[:12] == 'dlr_thrower.':
                message_id = msg.content.body
                try:
                    self.buffer.delivery(message_id)
                except Exception as e:
                    logger.error('Exception in update delivery time, %s %s' % (msg.routing_key, e,))
            else:
                try:
                    # no need Jasmin
                    body = msg.content.body if settings.USE_JASMIN else msg.content.body.replace('jasmin.vendor.', '')
                    pdu = pickle.loads(body)
                except Exception as e:
                    logger.error(
                        'Exception in parse pdu %s: %s\nContent body: %s' % (msg.routing_key, e, msg.content.body,))

                if not pdu:
                    chan.basic_ack(delivery_tag=msg.delivery_tag)
                    continue

                if msg.routing_key[:15] == 'submit.sm.resp.':
                    try:
                        self.buffer.submit_resp(props['message-id'])
                    except Exception as e:
                        logger.error('Exception in update submit response time, %s %s' % (msg.routing_key, e,))

                elif msg.routing_key[:10] == 'submit.sm.':
                    headers = props['headers']

                    routed_cid = msg.routing_key[10:]
                    source_connector = headers['source_connector']
                    short_message = pdu.params['short_message']
                    source_addr = pdu.params['source_addr']
                    destination_addr = pdu.params['destination_addr']

                    pdu_count, short_message = get_multipart_message(pdu, short_message)

                    submit_sm_bill = None
                    if settings.USE_JASMIN:
                        submit_sm_bill = pickle.loads(headers['submit_sm_bill']) \
                            if 'submit_sm_bill' in headers else None
                        if not submit_sm_bill:
                            logger.warning('empty submit_sm_bill in message %s' % (props['message-id'], ))

                    rate, uid = 0, None
                    if submit_sm_bill:
                        rate = submit_sm_bill.getTotalAmounts() * pdu_count
                        uid = submit_sm_bill.user.uid

                    # Преобразуем сообщение
                    if 'data_coding' in pdu.params \
                            and pdu.params['data_coding'] is not None:
                        short_message = decode_message(short_message, pdu.params['data_coding'])

                    # Преобразуем create_at в локальное время
                    create_time = utc_to_local(props['headers']['created_at'])

                    # Создаем новую запись
                    try:
                        source_id = self.buffer.get_source(source_addr)
                        operator_id = self.buffer.get_operator(routed_cid)

                        self.buffer.submit(props['message-id'], {
                            'message_id': props['message-id'],
                            'message': short_message,
                            'source_connector': source_connector,
                            'routed_cid': routed_cid,
                            'rate': rate,
                            'uid': uid,
                            'destination': destination_addr,
                            'pdu_count': pdu_count,
                            'status': str(pdu.status),
                            'create_time': create_time,
                            'submit_time': datetime.datetime.now(),
                            'submit_response_time': None,
                            'delivery_time': None,
                            'operator_id': operator_id,
                            'source_id': source_id
                        })
                    except Exception as e:
                        logger.error('Exception in create new sms, %s %s' % (msg.routing_key, e,))
                else:
                    logger.error('unknown route: %s' % (msg.routing_key,))

            chan.basic_ack(delivery_tag=msg.delivery_tag)

        if reactor.running:
            reactor.stop()

        self.buffer.close()

        logger.info('Shutdown')
