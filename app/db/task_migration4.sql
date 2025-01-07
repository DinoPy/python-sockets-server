DROP TABLE tasks;

CREATE TABLE tasks (
	id 			TEXT PRIMARY KEY,
	title		TEXT NOT NULL,
	description TEXT NOT NULL,
	created_at   DATE NOT NULL,
	completed_at DATE,
	duration 	TEXT NOT NULL,
	category    TEXT NOT NULL,
	tags 		TEXT,
	toggled_at  INTEGER,
	is_active   INTEGER NOT NULL,
	is_completed INTEGER NOT NULL,
	user_id 	TEXT NOT NULL,
	FOREIGN KEY(user_id) REFERENCES users(id)
);