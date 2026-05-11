-- Migration: Add province_code to city_info
-- Run on existing databases. Adds column and backfills from supported cities mapping.

\echo 'Adding province_code column to city_info...'
ALTER TABLE city_info ADD COLUMN IF NOT EXISTS province_code VARCHAR(10);

\echo 'Backfilling province_code for existing cities...'
UPDATE city_info SET province_code = 'CABA' WHERE country_code = 'AR' AND name = 'Buenos Aires';
UPDATE city_info SET province_code = 'CO' WHERE country_code = 'AR' AND name = 'Cordoba';
UPDATE city_info SET province_code = 'BA' WHERE country_code = 'AR' AND name = 'La Plata';
UPDATE city_info SET province_code = 'MN' WHERE country_code = 'AR' AND name = 'Mendoza';
UPDATE city_info SET province_code = 'MI' WHERE country_code = 'AR' AND name = 'Misiones';
UPDATE city_info SET province_code = 'SF' WHERE country_code = 'AR' AND name = 'Rosario';
UPDATE city_info SET province_code = 'TF' WHERE country_code = 'AR' AND name = 'Tierra del Fuego';
UPDATE city_info SET province_code = 'RJ' WHERE country_code = 'BR' AND name = 'Rio de Janeiro';
UPDATE city_info SET province_code = 'SP' WHERE country_code = 'BR' AND name = 'Sao Paulo';
UPDATE city_info SET province_code = 'RM' WHERE country_code = 'CL' AND name = 'Santiago';
UPDATE city_info SET province_code = 'CDMX' WHERE country_code = 'MX' AND name = 'Mexico DF';
UPDATE city_info SET province_code = 'NL' WHERE country_code = 'MX' AND name = 'Monterrey';
UPDATE city_info SET province_code = 'ARE' WHERE country_code = 'PE' AND name = 'Arequipa';
UPDATE city_info SET province_code = 'LIM' WHERE country_code = 'PE' AND name = 'Lima';
UPDATE city_info SET province_code = 'LAL' WHERE country_code = 'PE' AND name = 'Trujillo';
UPDATE city_info SET province_code = 'TX' WHERE country_code = 'US' AND name = 'Austin';
UPDATE city_info SET province_code = 'IL' WHERE country_code = 'US' AND name = 'Chicago';
UPDATE city_info SET province_code = 'CA' WHERE country_code = 'US' AND name = 'Los Angeles';
UPDATE city_info SET province_code = 'FL' WHERE country_code = 'US' AND name = 'Miami';
UPDATE city_info SET province_code = 'NY' WHERE country_code = 'US' AND name = 'New York';
UPDATE city_info SET province_code = 'CA' WHERE country_code = 'US' AND name = 'San Francisco';
UPDATE city_info SET province_code = 'WA' WHERE country_code = 'US' AND name = 'Seattle';
