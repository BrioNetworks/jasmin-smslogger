# -*- coding: utf-8 -*-
import pickle
import psycopg2

from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor
from twisted.internet.protocol import ClientCreator

from txamqp.protocol import AMQClient
from txamqp.client import TwistedDelegate
from txamqp.queue import Closed

from psycopg2 import Error

from smslogger import settings
from smslogger.utils import get_multipart_message, decode_message, utc_to_local
from smslogger.app_logger import logger


class SmsLogger(object):

    def __init__(self, amqp_conn, pg_conn, spec):
        self.amqp_conn = amqp_conn
        self.pg_conn = pg_conn
        self.spec = spec

    def start(self):
        vhost = self.amqp_conn['vhost']
        host = self.amqp_conn['host']
        port = self.amqp_conn['port']

        d = ClientCreator(reactor,
                          AMQClient,
                          delegate=TwistedDelegate(),
                          vhost=vhost,
                          spec=self.spec).connectTCP(host, port)

        d.addCallback(self.gotConnection)
        d.addErrback(self.whoops)

    def whoops(self, error):
        logger.error(error)
        if reactor.running:
            reactor.stop()

    @inlineCallbacks
    def gotConnection(self, conn):
        logger.info(u'Connected to broker')

        username = self.amqp_conn['user']
        password = self.amqp_conn['password']
        yield conn.start({"LOGIN": username, "PASSWORD": password})

        logger.info(u'Authenticated. Ready to receive messages')
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

        dbconn = psycopg2.connect(self.pg_conn)
        cursor = dbconn.cursor()

        # Ожидаем сообщения
        while True:
            try:
                msg = yield queue.get()
            except Closed:
                logger.info(u'Connection is closed!')
                break

            props = msg.content.properties

            if msg.routing_key[:12] == 'dlr_thrower.':
                sql = 'UPDATE public.sms_sms SET delivery_time=current_timestamp WHERE message_id=%s'
                message_id = msg.content.body
                data = (message_id,)
                try:
                    cursor.execute(sql, data)
                except Error as e:
                    logger.error(u'Exception in update delivery time, %s %s' % (msg.routing_key, e,))
            else:
                try:
                    # no need Jasmin
                    body = msg.content.body if settings.USE_JASMIN else msg.content.body.replace('jasmin.vendor.', '')
                    pdu = pickle.loads(body)
                except Exception as e:
                    logger.error(
                        u'Exception in parse pdu %s: %s\nContent body: %s' % (msg.routing_key, e, msg.content.body,))

                if not pdu:
                    chan.basic_ack(delivery_tag=msg.delivery_tag)
                    continue

                if msg.routing_key[:10] == 'submit.sm.':
                    headers = props['headers']

                    routed_cid = msg.routing_key[10:]

                    source_connector = headers['source_connector'] \
                        if 'source_connector' in headers else None

                    short_message = pdu.params['short_message'] \
                        if 'short_message' in pdu.params else None

                    pdu_count, short_message = get_multipart_message(pdu, short_message)

                    submit_sm_bill = pickle.loads(headers['submit_sm_bill']) \
                        if 'submit_sm_bill' in headers else None
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

                    source_addr = pdu.params['source_addr'] \
                        if 'source_addr' in pdu.params else None

                    destination_addr = pdu.params['destination_addr'] \
                        if 'destination_addr' in pdu.params else None

                    # Создаем новую запись
                    sql = 'SELECT public.add_sms (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);'
                    data = (props['message-id'],
                            short_message,
                            source_connector,
                            routed_cid,
                            rate,
                            uid,
                            source_addr,
                            destination_addr,
                            pdu_count,
                            str(pdu.status),
                            create_time)
                    try:
                        cursor.execute(sql, data)
                    except Error as e:
                        logger.error(u'Exception in create new sms, %s %s' % (msg.routing_key, e,))

                elif msg.routing_key[:15] == 'submit.sm.resp.':
                    # Обновляем время ответа
                    sql = 'UPDATE public.sms_sms SET submit_response_time=current_timestamp WHERE message_id=%s'
                    data = (props['message-id'],)
                    try:
                        cursor.execute(sql, data)
                    except Error as e:
                        logger.error(u'Exception in update submit response time, %s %s' % (msg.routing_key, e,))
                else:
                    logger.error(u'unknown route: %s' % (msg.routing_key,))

            dbconn.commit()

            chan.basic_ack(delivery_tag=msg.delivery_tag)

        cursor.close()
        dbconn.close()

        if reactor.running:
            reactor.stop()

        logger.info(u'Shutdown')
