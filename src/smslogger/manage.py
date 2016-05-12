from twisted.internet import reactor
from smslogger.sms_logger import SmsLogger


def main():
    SmsLogger().start()
    reactor.run()

if __name__ == "__main__":
    main()
