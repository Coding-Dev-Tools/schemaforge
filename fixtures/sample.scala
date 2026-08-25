import java.time.{Instant, LocalDate, LocalTime}
import java.util.UUID

case class User(
    id: Int,
    name: String,
    email: String,
    role: String = "viewer",
    isActive: Boolean = true,
    createdAt: Instant
)

case class Post(
    id: Int,
    title: String,
    content: Option[String],
    authorId: Int,
    status: String = "draft"
)
