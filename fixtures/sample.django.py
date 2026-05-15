"""
SchemaForge Demo: Blog Schema (Django Models)
Convert to any ORM format with: schemaforge convert --from django --to <format> --input fixtures/sample.django.py
"""

from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    EDITOR = 'editor', 'Editor'
    AUTHOR = 'author', 'Author'
    SUBSCRIBER = 'subscriber', 'Subscriber'


class User(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.SUBSCRIBER,
    )
    bio = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True)
    content = models.TextField()
    excerpt = models.TextField(null=True, blank=True, max_length=500)
    status = models.CharField(max_length=20, default='draft')
    published_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posts',
    )
    view_count = models.IntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'posts'

    def __str__(self):
        return self.title
