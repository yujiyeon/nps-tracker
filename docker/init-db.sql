-- TimescaleDB 확장 활성화 (timescale/timescaledb 이미지는 확장이 설치돼 있으나 활성화는 별도 필요)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 테스트용 DB 생성 (테스트에서 nps_tracker_test 사용)
CREATE DATABASE nps_tracker_test;
GRANT ALL PRIVILEGES ON DATABASE nps_tracker_test TO nps_user;
