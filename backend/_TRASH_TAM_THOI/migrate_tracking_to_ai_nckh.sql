-- ============================================================
-- Tích hợp các bảng tracking_db vào ai_nckh
-- Sử dụng CREATE TABLE IF NOT EXISTS để an toàn
-- ============================================================

USE ai_nckh;

-- 1. SESSIONS (bảng cha - tạo trước)
CREATE TABLE IF NOT EXISTS `sessions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `session_id` varchar(100) NOT NULL COMMENT 'ID phien duy nhat',
  `start_time` datetime NOT NULL COMMENT 'Thoi gian bat dau',
  `end_time` datetime DEFAULT NULL COMMENT 'Thoi gian ket thuc',
  `status` enum('active','completed','error') DEFAULT 'active' COMMENT 'Trang thai',
  `video_source` varchar(500) DEFAULT NULL COMMENT 'Nguon video (webcam/file path)',
  `device` varchar(50) DEFAULT NULL COMMENT 'Thiet bi xu ly (cuda/cpu)',
  `total_persons_detected` int(11) DEFAULT 0,
  `total_intrusions` int(11) DEFAULT 0,
  `total_videos` int(11) DEFAULT 0,
  `total_images` int(11) DEFAULT 0,
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `session_id` (`session_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_start_time` (`start_time`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Luu thong tin phien lam viec';

-- 2. SETTINGS
CREATE TABLE IF NOT EXISTS `settings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) NOT NULL COMMENT 'Ten cai dat',
  `setting_value` text DEFAULT NULL COMMENT 'Gia tri',
  `setting_type` enum('string','int','float','bool','json') DEFAULT 'string',
  `description` text DEFAULT NULL COMMENT 'Mo ta',
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `setting_key` (`setting_key`),
  KEY `idx_setting_key` (`setting_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Cai dat he thong';

-- 3. PERSONS
CREATE TABLE IF NOT EXISTS `persons` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `person_id` int(11) NOT NULL COMMENT 'ID nguoi (tu tracker)',
  `session_id` varchar(100) NOT NULL COMMENT 'Thuoc phien nao',
  `first_seen` datetime NOT NULL COMMENT 'Lan dau xuat hien',
  `last_seen` datetime DEFAULT NULL COMMENT 'Lan cuoi xuat hien',
  `total_frames` int(11) DEFAULT 0,
  `is_intruder` tinyint(1) DEFAULT 0,
  `intrusion_count` int(11) DEFAULT 0,
  `avg_confidence` decimal(5,4) DEFAULT NULL,
  `color_features` longtext DEFAULT NULL COMMENT 'Dac trung mau sac (JSON)',
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_person_id` (`person_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_is_intruder` (`is_intruder`),
  KEY `idx_first_seen` (`first_seen`),
  CONSTRAINT `persons_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Luu thong tin nguoi duoc phat hien';

-- 4. ZONES
CREATE TABLE IF NOT EXISTS `zones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `zone_id` int(11) NOT NULL COMMENT 'ID vung',
  `session_id` varchar(100) NOT NULL COMMENT 'Thuoc phien nao',
  `zone_name` varchar(100) DEFAULT NULL COMMENT 'Ten vung',
  `points` longtext NOT NULL COMMENT 'Toa do cac diem (JSON)',
  `color` varchar(20) DEFAULT '#FF0000',
  `is_active` tinyint(1) DEFAULT 1,
  `intrusion_count` int(11) DEFAULT 0,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_zone_id` (`zone_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_is_active` (`is_active`),
  CONSTRAINT `zones_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Luu thong tin vung cam';

-- 5. VIDEOS
CREATE TABLE IF NOT EXISTS `videos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `video_id` varchar(100) NOT NULL COMMENT 'ID video duy nhat',
  `session_id` varchar(100) NOT NULL COMMENT 'Thuoc phien nao',
  `video_type` enum('universal','intrusion') NOT NULL COMMENT 'Loai video',
  `file_path` varchar(500) NOT NULL COMMENT 'Duong dan file',
  `file_name` varchar(255) NOT NULL COMMENT 'Ten file',
  `file_size` bigint(20) DEFAULT 0,
  `duration` decimal(10,2) DEFAULT 0.00,
  `fps` decimal(5,2) DEFAULT 20.00,
  `width` int(11) DEFAULT 0,
  `height` int(11) DEFAULT 0,
  `codec` varchar(20) DEFAULT 'mp4v',
  `total_frames` int(11) DEFAULT 0,
  `start_time` datetime NOT NULL,
  `end_time` datetime DEFAULT NULL,
  `person_ids` longtext DEFAULT NULL COMMENT 'JSON array',
  `person_count` int(11) DEFAULT 0,
  `has_intrusion` tinyint(1) DEFAULT 0,
  `intrusion_zones` longtext DEFAULT NULL COMMENT 'JSON array',
  `thumbnail_path` varchar(500) DEFAULT NULL,
  `telegram_sent` tinyint(1) DEFAULT 0,
  `telegram_sent_at` datetime DEFAULT NULL,
  `telegram_message_id` varchar(100) DEFAULT NULL,
  `telegram_error` text DEFAULT NULL,
  `status` enum('recording','completed','error','deleted') DEFAULT 'recording',
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `video_id` (`video_id`),
  KEY `idx_video_id` (`video_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_video_type` (`video_type`),
  KEY `idx_start_time` (`start_time`),
  KEY `idx_status` (`status`),
  KEY `idx_telegram_sent` (`telegram_sent`),
  KEY `idx_has_intrusion` (`has_intrusion`),
  CONSTRAINT `videos_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Luu thong tin video quay duoc';

-- 6. IMAGES
CREATE TABLE IF NOT EXISTS `images` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `image_id` varchar(100) NOT NULL,
  `session_id` varchar(100) NOT NULL,
  `video_id` varchar(100) DEFAULT NULL,
  `image_type` enum('intrusion_alert','detection','snapshot','thumbnail') NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_name` varchar(255) NOT NULL,
  `file_size` int(11) DEFAULT 0,
  `width` int(11) DEFAULT 0,
  `height` int(11) DEFAULT 0,
  `capture_time` datetime NOT NULL,
  `person_id` int(11) DEFAULT NULL,
  `person_ids` longtext DEFAULT NULL COMMENT 'JSON array',
  `bbox` longtext DEFAULT NULL COMMENT 'JSON [x1, y1, x2, y2]',
  `confidence` decimal(5,4) DEFAULT NULL,
  `zone_id` int(11) DEFAULT NULL,
  `zone_name` varchar(100) DEFAULT NULL,
  `is_intrusion` tinyint(1) DEFAULT 0,
  `telegram_sent` tinyint(1) DEFAULT 0,
  `telegram_sent_at` datetime DEFAULT NULL,
  `telegram_message_id` varchar(100) DEFAULT NULL,
  `telegram_error` text DEFAULT NULL,
  `status` enum('active','deleted') DEFAULT 'active',
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `image_id` (`image_id`),
  KEY `idx_image_id` (`image_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_video_id` (`video_id`),
  KEY `idx_image_type` (`image_type`),
  KEY `idx_capture_time` (`capture_time`),
  KEY `idx_person_id` (`person_id`),
  KEY `idx_is_intrusion` (`is_intrusion`),
  KEY `idx_telegram_sent` (`telegram_sent`),
  CONSTRAINT `images_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`) ON DELETE CASCADE,
  CONSTRAINT `images_ibfk_2` FOREIGN KEY (`video_id`) REFERENCES `videos` (`video_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Luu thong tin hinh anh canh bao';

-- 7. EVENTS
CREATE TABLE IF NOT EXISTS `events` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `event_id` varchar(100) NOT NULL,
  `session_id` varchar(100) NOT NULL,
  `event_type` enum('system_start','system_stop','person_detected','person_left','intrusion_start','intrusion_end','recording_start','recording_stop','telegram_sent','telegram_failed','zone_created','zone_deleted','error','warning','info') NOT NULL,
  `event_time` datetime NOT NULL,
  `person_id` int(11) DEFAULT NULL,
  `person_ids` longtext DEFAULT NULL COMMENT 'JSON array',
  `zone_id` int(11) DEFAULT NULL,
  `zone_name` varchar(100) DEFAULT NULL,
  `video_id` varchar(100) DEFAULT NULL,
  `image_id` varchar(100) DEFAULT NULL,
  `severity` enum('debug','info','warning','error','critical') DEFAULT 'info',
  `description` text DEFAULT NULL,
  `metadata` longtext DEFAULT NULL COMMENT 'JSON',
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `event_id` (`event_id`),
  KEY `idx_event_id` (`event_id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_event_type` (`event_type`),
  KEY `idx_event_time` (`event_time`),
  KEY `idx_severity` (`severity`),
  KEY `idx_person_id` (`person_id`),
  CONSTRAINT `events_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Luu cac su kien he thong';

-- 8. INTRUSION_EVENTS
CREATE TABLE IF NOT EXISTS `intrusion_events` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `duration_seconds` float DEFAULT NULL,
  `total_intruders` int(11) DEFAULT NULL,
  `video_file_path` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. INTRUSION_SNAPSHOTS
CREATE TABLE IF NOT EXISTS `intrusion_snapshots` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `event_id` int(11) DEFAULT NULL,
  `person_id` int(11) DEFAULT NULL,
  `image_file_path` varchar(255) DEFAULT NULL,
  `capture_time` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `event_id` (`event_id`),
  CONSTRAINT `intrusion_snapshots_ibfk_1` FOREIGN KEY (`event_id`) REFERENCES `intrusion_events` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. TELEGRAM_QUEUE
CREATE TABLE IF NOT EXISTS `telegram_queue` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `message_type` enum('text','photo','video','document') NOT NULL,
  `content_path` varchar(500) DEFAULT NULL,
  `caption` text DEFAULT NULL,
  `video_id` varchar(100) DEFAULT NULL,
  `image_id` varchar(100) DEFAULT NULL,
  `status` enum('pending','sending','sent','failed') DEFAULT 'pending',
  `retry_count` int(11) DEFAULT 0,
  `max_retries` int(11) DEFAULT 3,
  `error_message` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `sent_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_video_id` (`video_id`),
  KEY `idx_image_id` (`image_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Hang doi gui message Telegram';

-- 11. DAILY_STATISTICS
CREATE TABLE IF NOT EXISTS `daily_statistics` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `stat_date` date NOT NULL,
  `total_sessions` int(11) DEFAULT 0,
  `total_persons` int(11) DEFAULT 0,
  `total_intrusions` int(11) DEFAULT 0,
  `total_videos` int(11) DEFAULT 0,
  `total_images` int(11) DEFAULT 0,
  `total_video_duration` decimal(12,2) DEFAULT 0.00,
  `total_storage_bytes` bigint(20) DEFAULT 0,
  `peak_hour` int(11) DEFAULT NULL,
  `peak_intrusions` int(11) DEFAULT 0,
  `notes` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `stat_date` (`stat_date`),
  KEY `idx_stat_date` (`stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Thong ke theo ngay';

-- ============================================================
-- VIEWS
-- ============================================================

-- View: Thong ke video theo ngay
CREATE OR REPLACE VIEW `v_daily_stats` AS 
SELECT 
  CAST(`videos`.`start_time` AS DATE) AS `date`,
  COUNT(0) AS `video_count`,
  SUM(CASE WHEN `videos`.`video_type` = 'universal' THEN 1 ELSE 0 END) AS `universal_count`,
  SUM(CASE WHEN `videos`.`video_type` = 'intrusion' THEN 1 ELSE 0 END) AS `intrusion_count`,
  ROUND(SUM(`videos`.`duration`),2) AS `total_duration`,
  ROUND(SUM(`videos`.`file_size`) / 1024 / 1024,2) AS `total_size_mb`,
  SUM(`videos`.`person_count`) AS `total_persons` 
FROM `videos` 
WHERE `videos`.`status` = 'completed' 
GROUP BY CAST(`videos`.`start_time` AS DATE) 
ORDER BY CAST(`videos`.`start_time` AS DATE) DESC;

-- View: Chi tiet video
CREATE OR REPLACE VIEW `v_videos_detail` AS 
SELECT 
  `v`.`id`, `v`.`video_id`, `v`.`session_id`, `v`.`video_type`,
  `v`.`file_path`, `v`.`file_name`, `v`.`file_size`, `v`.`duration`,
  `v`.`fps`, `v`.`width`, `v`.`height`, `v`.`codec`, `v`.`total_frames`,
  `v`.`start_time`, `v`.`end_time`, `v`.`person_ids`, `v`.`person_count`,
  `v`.`has_intrusion`, `v`.`intrusion_zones`, `v`.`thumbnail_path`,
  `v`.`telegram_sent`, `v`.`telegram_sent_at`, `v`.`telegram_message_id`,
  `v`.`telegram_error`, `v`.`status`, `v`.`notes`,
  `v`.`created_at`, `v`.`updated_at`,
  `s`.`video_source`, `s`.`device`,
  ROUND(`v`.`file_size` / 1024 / 1024, 2) AS `file_size_mb`,
  TIMESTAMPDIFF(SECOND, `v`.`start_time`, `v`.`end_time`) AS `actual_duration`
FROM `videos` `v` 
JOIN `sessions` `s` ON `v`.`session_id` = `s`.`session_id`
WHERE `v`.`status` = 'completed';

-- ============================================================
-- DONE! Tat ca bang tracking_db da duoc tich hop vao ai_nckh
-- ============================================================
