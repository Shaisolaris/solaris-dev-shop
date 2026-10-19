ALTER TABLE orders ADD COLUMN note TEXT NOT NULL DEFAULT '';
UPDATE orders SET note = 'migrated r2';
PRAGMA user_version = 2;
