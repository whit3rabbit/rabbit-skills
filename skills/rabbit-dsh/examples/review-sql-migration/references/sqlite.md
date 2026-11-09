# SQLite migration review

- Compare the before and after definitions. Check existing rows when a change adds a required value, a uniqueness constraint, or a foreign key.
- Find both sides of new foreign keys. Check the parent key and whether an existing child index starts with the foreign-key columns. SQLite can scan the child table when checking parent deletes or key updates without a suitable child index.
- For a table rebuild, check the column mapping, data copy, constraints, index recreation, and transaction boundaries. Flag missing context when the file alone cannot establish safety.
- Report what to verify in a disposable database. Use representative rows and exercise both a valid write and a constraint violation.

[SQLite foreign-key index guidance](https://www.sqlite.org/foreignkeys.html#fk_indexes)
