ALTER TABLE orders
  ADD COLUMN customer_id INTEGER REFERENCES customers(id);
