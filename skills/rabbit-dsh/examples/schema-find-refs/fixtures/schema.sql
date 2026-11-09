CREATE TABLE customers (
  id INTEGER PRIMARY KEY
);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL
);

CREATE INDEX orders_by_created_at ON orders(created_at);
