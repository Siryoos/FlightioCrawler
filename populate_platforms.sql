-- Populate platforms table with airline sites from FlightioCrawler
-- This script inserts all the supported airline platforms

SET search_path TO crawler, public;

-- Clear existing platforms for fresh setup
DELETE FROM platforms;

-- Iranian Airlines
INSERT INTO platforms (platform_code, platform_name, platform_type, base_url, requires_persian_processing, rate_limit_config, anti_bot_measures, is_active) VALUES

-- Iranian Aggregators
('alibaba', 'Alibaba', 'aggregator', 'https://www.alibaba.ir', true, 
 '{"requests_per_minute": 10, "delay_seconds": 6}', 
 '{"cloudflare": true, "captcha": true, "user_agent_rotation": true}', true),

('flytoday', 'FlyToday', 'aggregator', 'https://www.flytoday.ir', true,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"anti_bot": true, "rate_limiting": true}', true),

('snapptrip', 'SnappTrip', 'aggregator', 'https://www.snapptrip.com', true,
 '{"requests_per_minute": 12, "delay_seconds": 5}', 
 '{"advanced_detection": true, "captcha": true}', true),

('safarmarket', 'Safarmarket', 'aggregator', 'https://www.safarmarket.com', true,
 '{"requests_per_minute": 10, "delay_seconds": 6}', 
 '{"cloudflare": true}', true),

('mz724', 'MZ724', 'aggregator', 'https://www.724.ir', true,
 '{"requests_per_minute": 8, "delay_seconds": 7}', 
 '{"strict_anti_bot": true, "ip_blocking": true}', true),

-- Iranian Airlines Direct
('iran_air', 'Iran Air', 'iranian_airline', 'https://www.iranair.com', true,
 '{"requests_per_minute": 20, "delay_seconds": 3}', 
 '{"basic_protection": true}', true),

('mahan_air', 'Mahan Air', 'iranian_airline', 'https://www.mahan.aero', true,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"cloudflare": true}', true),

('kish_air', 'Kish Air', 'iranian_airline', 'https://www.kishair.com', true,
 '{"requests_per_minute": 18, "delay_seconds": 3}', 
 '{"basic_protection": true}', true),

('zagros_air', 'Zagros Air', 'iranian_airline', 'https://www.zagrosjet.ir', true,
 '{"requests_per_minute": 16, "delay_seconds": 4}', 
 '{"basic_protection": true}', true),

('caspian_air', 'Caspian Air', 'iranian_airline', 'https://www.caspianair.com', true,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"basic_protection": true}', true),

('aseman_air', 'Aseman Airlines', 'iranian_airline', 'https://www.asemanairlines.com', true,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"basic_protection": true}', true),

('ata_air', 'ATA Airlines', 'iranian_airline', 'https://www.ata.ir', true,
 '{"requests_per_minute": 12, "delay_seconds": 5}', 
 '{"basic_protection": true}', true),

('qeshm_air', 'Qeshm Air', 'iranian_airline', 'https://www.qeshm-air.com', true,
 '{"requests_per_minute": 14, "delay_seconds": 4}', 
 '{"basic_protection": true}', true),

('sepehran_air', 'Sepehran Airlines', 'iranian_airline', 'https://www.sepehranair.ir', true,
 '{"requests_per_minute": 12, "delay_seconds": 5}', 
 '{"basic_protection": true}', true),

('taban_air', 'Taban Air', 'iranian_airline', 'https://www.tabanair.ir', true,
 '{"requests_per_minute": 14, "delay_seconds": 4}', 
 '{"basic_protection": true}', true),

('varesh_air', 'Varesh Airlines', 'iranian_airline', 'https://www.varesh.aero', true,
 '{"requests_per_minute": 12, "delay_seconds": 5}', 
 '{"basic_protection": true}', true),

('karun_air', 'Karun Air', 'iranian_airline', 'https://www.karunair.com', true,
 '{"requests_per_minute": 14, "delay_seconds": 4}', 
 '{"basic_protection": true}', true),

-- Booking Platforms
('parto_crs', 'Parto CRS', 'aggregator', 'https://crs.parto.ir', true,
 '{"requests_per_minute": 8, "delay_seconds": 7}', 
 '{"advanced_protection": true}', true),

('parto_ticket', 'Parto Ticket', 'aggregator', 'https://ticket.parto.ir', true,
 '{"requests_per_minute": 8, "delay_seconds": 7}', 
 '{"advanced_protection": true}', true),

('book_charter', 'Book Charter', 'aggregator', 'https://www.bookcharter.ir', true,
 '{"requests_per_minute": 10, "delay_seconds": 6}', 
 '{"cloudflare": true}', true),

('book_charter_724', 'Book Charter 724', 'aggregator', 'https://724.bookcharter.ir', true,
 '{"requests_per_minute": 8, "delay_seconds": 7}', 
 '{"advanced_protection": true}', true),

('flightio', 'Flightio', 'aggregator', 'https://flightio.com', false,
 '{"requests_per_minute": 12, "delay_seconds": 5}', 
 '{"cloudflare": true}', true),

-- International Airlines (for future expansion)
('emirates', 'Emirates', 'international_airline', 'https://www.emirates.com', false,
 '{"requests_per_minute": 20, "delay_seconds": 3}', 
 '{"advanced_protection": true}', false),

('turkish_airlines', 'Turkish Airlines', 'international_airline', 'https://www.turkishairlines.com', false,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"cloudflare": true}', false),

('lufthansa', 'Lufthansa', 'international_airline', 'https://www.lufthansa.com', false,
 '{"requests_per_minute": 20, "delay_seconds": 3}', 
 '{"advanced_protection": true}', false),

('air_france', 'Air France', 'international_airline', 'https://www.airfrance.com', false,
 '{"requests_per_minute": 18, "delay_seconds": 3}', 
 '{"advanced_protection": true}', false),

('british_airways', 'British Airways', 'international_airline', 'https://www.britishairways.com', false,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"advanced_protection": true}', false),

('klm', 'KLM', 'international_airline', 'https://www.klm.com', false,
 '{"requests_per_minute": 18, "delay_seconds": 3}', 
 '{"advanced_protection": true}', false),

('etihad_airways', 'Etihad Airways', 'international_airline', 'https://www.etihad.com', false,
 '{"requests_per_minute": 16, "delay_seconds": 4}', 
 '{"advanced_protection": true}', false),

('qatar_airways', 'Qatar Airways', 'international_airline', 'https://www.qatarairways.com', false,
 '{"requests_per_minute": 15, "delay_seconds": 4}', 
 '{"advanced_protection": true}', false),

('pegasus', 'Pegasus Airlines', 'international_airline', 'https://www.flypgs.com', false,
 '{"requests_per_minute": 20, "delay_seconds": 3}', 
 '{"cloudflare": true}', false);

-- Initialize crawler status for all active platforms
INSERT INTO crawler_status (platform_id, status, crawl_count, success_count, error_count)
SELECT platform_id, 'stopped', 0, 0, 0 
FROM platforms 
WHERE is_active = true;

-- Show inserted platforms
SELECT platform_code, platform_name, platform_type, is_active 
FROM platforms 
ORDER BY platform_type, platform_name;

-- Show summary
SELECT 
    platform_type,
    COUNT(*) as total_platforms,
    COUNT(*) FILTER (WHERE is_active = true) as active_platforms
FROM platforms 
GROUP BY platform_type
ORDER BY platform_type; 