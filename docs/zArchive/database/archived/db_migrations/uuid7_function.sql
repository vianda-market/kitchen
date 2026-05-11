-- ARCHIVED: UUID7 Generation Function for PostgreSQL < 18
-- Archived: 2026-03-14 — PostgreSQL 18+ has built-in uuidv7(). Use native function.
-- This file is kept for reference when running on PostgreSQL 14–17. For PG 18+, no action needed.

-- Drop function if exists (for rebuilds)
DROP FUNCTION IF EXISTS uuidv7() CASCADE;

CREATE OR REPLACE FUNCTION uuidv7()
RETURNS UUID AS $$
DECLARE
    unix_ts_ms BIGINT;
    uuid_bytes BYTEA;
    random_part BYTEA;
BEGIN
    -- Get current timestamp in milliseconds
    unix_ts_ms := EXTRACT(EPOCH FROM clock_timestamp()) * 1000;
    
    -- Generate random UUID for the random part and convert to bytea
    -- Convert UUID to hex string (without dashes) then decode to bytea
    random_part := decode(replace(gen_random_uuid()::text, '-', ''), 'hex');
    
    -- Build UUID7 bytes:
    -- Bytes 0-5: 48-bit timestamp (milliseconds since Unix epoch)
    -- Byte 6: Version (112 = 0x70 = version 7) + 4 bits of timestamp
    -- Byte 7: Variant (128 = 0x80 = RFC 4122) + 2 bits of timestamp
    -- Bytes 8-15: Random data from gen_random_uuid()
    
    uuid_bytes := 
        set_byte(
            set_byte(
                set_byte(
                    set_byte(
                        set_byte(
                            set_byte(
                                set_byte(
                                    set_byte(
                                        set_byte(
                                            set_byte(
                                                set_byte(
                                                    set_byte(
                                                        set_byte(
                                                            set_byte(
                                                set_byte(
                                                    random_part,
                                                    0, ((unix_ts_ms >> 40) & 255)::integer
                                                ),
                                                1, ((unix_ts_ms >> 32) & 255)::integer
                                            ),
                                            2, ((unix_ts_ms >> 24) & 255)::integer
                                        ),
                                        3, ((unix_ts_ms >> 16) & 255)::integer
                                    ),
                                    4, ((unix_ts_ms >> 8) & 255)::integer
                                ),
                                5, (unix_ts_ms & 255)::integer
                            ),
                            6, (((unix_ts_ms >> 56) & 15) | 112)::integer
                        ),
                        7, (((unix_ts_ms >> 48) & 63) | 128)::integer
                                    ),
                                    8, get_byte(random_part, 8)
                                ),
                                9, get_byte(random_part, 9)
                            ),
                            10, get_byte(random_part, 10)
                        ),
                        11, get_byte(random_part, 11)
                    ),
                    12, get_byte(random_part, 12)
                ),
                13, get_byte(random_part, 13)
            ),
            14, get_byte(random_part, 14)
        );
    
    uuid_bytes := set_byte(uuid_bytes, 15, get_byte(random_part, 15));
    
    -- Convert bytea to UUID
    RETURN encode(uuid_bytes, 'hex')::uuid;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION uuidv7() TO PUBLIC;

-- Test the function
DO $$
DECLARE
    test_uuid UUID;
    test_uuid2 UUID;
BEGIN
    test_uuid := uuidv7();
    PERFORM pg_sleep(0.001); -- Wait 1ms
    test_uuid2 := uuidv7();
    
    -- Verify UUID7 is time-ordered (second should be greater)
    IF test_uuid2 > test_uuid THEN
        RAISE NOTICE '✅ UUID7 function working correctly - time-ordered';
    ELSE
        RAISE WARNING '⚠️ UUID7 may not be time-ordered correctly';
    END IF;
END $$;
