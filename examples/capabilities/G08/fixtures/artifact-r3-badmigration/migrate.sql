PRAGMA user_version = 3;
UPDATE orders SET total_cents = 0;
INSERT INTO orders (id, customer, total_cents) VALUES (1, 'duplicate-key', 1);
