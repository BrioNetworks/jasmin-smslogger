import txamqp.spec

from twisted.internet import reactor

from smslogger import settings
from smslogger.sms_logger import SmsLogger


def main():
    spec = txamqp.spec.load(settings.AMQP_SPECIFICATION)

    SmsLogger(settings.AMQP_CONNECTION, settings.PG_CONNECTION, spec).start()

    reactor.run()

if __name__ == "__main__":
    main()
