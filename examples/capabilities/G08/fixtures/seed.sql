CREATE TABLE orders (id INTEGER PRIMARY KEY, customer TEXT NOT NULL, total_cents INTEGER NOT NULL);
INSERT INTO orders (customer, total_cents) VALUES ('harbor-cafe', 1250), ('pier-books', 4800), ('dock-gym', 990);
