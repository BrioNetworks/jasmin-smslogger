CHECK_CONNECTION = 'SELECT 0'

SELECT_SOURCES = 'SELECT id, address FROM PUBLIC.sms_source;'

SELECT_OPERATORS = 'SELECT id, routed_cid FROM public.sms_operator;'

SELECT_OR_INSERT_SOURCE = \
    '''WITH s AS (
        SELECT id
        FROM sms_source
        WHERE address = %s or (%s is NULL and address is NULL)
        ORDER BY address
        LIMIT 1
      ), i AS (
        INSERT INTO sms_source (address)
        SELECT %s
        WHERE NOT EXISTS (SELECT 1 FROM s)
        RETURNING id
        )
    SELECT id FROM i
    UNION ALL
    SELECT id FROM s;'''

INSERT_UNKNOWN_OPERATOR = "INSERT INTO sms_operator (routed_cid, name) VALUES (%s, %s) RETURNING id;"
