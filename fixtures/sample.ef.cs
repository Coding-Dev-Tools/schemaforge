using System;
using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace SchemaForge.Models;

[Table("users")]
public class User
{
    [Key]
    public int Id { get; set; }

    [Required]
    [MaxLength(100)]
    public string Name { get; set; }

    [Required]
    public string Email { get; set; }

    public bool IsActive { get; set; }

    public DateTime CreatedAt { get; set; }
}

[Table("posts")]
public class Post
{
    [Key]
    public int Id { get; set; }

    [Required]
    [MaxLength(200)]
    public string Title { get; set; }

    public string? Content { get; set; }

    public int AuthorId { get; set; }

    [MaxLength(20)]
    public string? Status { get; set; }
}

public enum Role
{
    Admin,
    Editor,
    Viewer
}
