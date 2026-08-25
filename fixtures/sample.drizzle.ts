// SchemaForge Demo: Blog Schema (Drizzle ORM — PostgreSQL)
// Convert to any ORM format with: schemaforge convert --from drizzle --to <format> --input fixtures/sample.drizzle.ts

import { pgTable, pgEnum, serial, varchar, text, integer, boolean, timestamp, decimal } from 'drizzle-orm/pg-core';

// ── Enums ──

export const userRole = pgEnum('user_role', ['admin', 'editor', 'author', 'subscriber']);

// ── Tables ──

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 100 }).notNull(),
  email: varchar('email', { length: 255 }).notNull().unique(),
  role: userRole('role').default('subscriber'),
  bio: text('bio'),
  isActive: boolean('is_active').default(true),
  createdAt: timestamp('created_at').defaultNow(),
});

export const categories = pgTable('categories', {
  id: serial('id').primaryKey(),
  name: varchar('name', { length: 100 }).notNull().unique(),
  description: text('description'),
  sortOrder: integer('sort_order').default(0),
});

export const posts = pgTable('posts', {
  id: serial('id').primaryKey(),
  title: varchar('title', { length: 200 }).notNull(),
  slug: varchar('slug', { length: 255 }).notNull().unique(),
  content: text('content').notNull(),
  excerpt: varchar('excerpt', { length: 500 }),
  status: varchar('status', { length: 20 }).default('draft'),
  publishedAt: timestamp('published_at'),
  authorId: integer('author_id').notNull().references(() => users.id),
  categoryId: integer('category_id').references(() => categories.id),
  viewCount: integer('view_count').default(0),
  rating: decimal('rating', { precision: 3, scale: 2 }).default('0.00'),
  createdAt: timestamp('created_at').defaultNow(),
  updatedAt: timestamp('updated_at').defaultNow(),
});
