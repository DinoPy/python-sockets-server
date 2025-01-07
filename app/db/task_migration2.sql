CREATE TABLE tasks (
	id 			TEXT PRIMARY KEY,
	name		TEXT NOT NULL,
	description TEXT NOT NULL,
	createdAt   DATE NOT NULL,
	completedAt DATE,
	duration 	TEXT NOT NULL,
	category    TEXT NOT NULL,
	tags 		TEXT
);