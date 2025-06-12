from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
from typing import Optional, List
import datetime

# Forward declarations for type hinting
class ProgrammingLanguage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    slug: str = Field(unique=True, index=True) # e.g., "python", "rust"

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(unique=True, index=True)
    ui_language_code: str = Field(default="ru") # For bot interface language
    active_language_id: Optional[int] = Field(default=None, foreign_key="programminglanguage.id")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    state: str = Field(default="lang_select")  # Текущее состояние пользователя (для state machine)

    active_language: Optional[ProgrammingLanguage] = Relationship()
    progress_records: List["UserProgress"] = Relationship(back_populates="user")
    answers: List["UserAnswer"] = Relationship(back_populates="user") # All answers by user across all languages

class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = Field(default=None)

class Question(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    category_id: int = Field(foreign_key="category.id")
    language_id: int = Field(foreign_key="programminglanguage.id")
    is_diagnostic: bool = Field(default=False)
    author_notes: Optional[str] = Field(default=None) # e.g., correct answer hints, internal notes

    category: Optional[Category] = Relationship()
    language: Optional[ProgrammingLanguage] = Relationship()

class UserProgress(SQLModel, table=True):
    __tablename__ = "userprogress" # Explicit table name to avoid potential conflicts
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    language_id: int = Field(foreign_key="programminglanguage.id", index=True)
    diagnostic_scores_json: Optional[str] = Field(default=None) # JSON string for self-assessment scores
    diagnostics_completed: bool = Field(default=False) # Явно отмечает завершение диагностики
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow, sa_column_kwargs={"onupdate": datetime.datetime.utcnow})

    user: Optional[User] = Relationship(back_populates="progress_records")
    language: Optional[ProgrammingLanguage] = Relationship()
    learning_plan_items: List["UserLearningPlanItem"] = Relationship(back_populates="user_progress")

    __table_args__ = (UniqueConstraint("user_id", "language_id", name="uq_user_language_progress"),)

class UserLearningPlanItem(SQLModel, table=True):
    __tablename__ = "userlearningplanitem"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_progress_id: int = Field(foreign_key="userprogress.id", index=True)
    question_id: int = Field(foreign_key="question.id")
    order_index: int # Sequence of the question in this specific plan
    status: str = Field(default="pending") # e.g., "pending", "current", "answered", "skipped"
    assigned_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    user_progress: Optional[UserProgress] = Relationship(back_populates="learning_plan_items")
    question: Optional[Question] = Relationship()

class UserAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id") # Direct link to user for easier querying of all user's answers
    question_id: int = Field(foreign_key="question.id")
    learning_plan_item_id: int = Field(foreign_key="userlearningplanitem.id") # Link to the specific instance in a plan
    answer_text: str
    llm_assessment: Optional[str] = Field(default=None) # AI's textual feedback on the answer
    llm_explanation: Optional[str] = Field(default=None) # AI's detailed explanation of the topic
    is_correct_by_llm: Optional[bool] = Field(default=None) # If AI can provide a boolean correct/incorrect
    answered_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="answers")
    question: Optional[Question] = Relationship()
    learning_plan_item: Optional[UserLearningPlanItem] = Relationship()


class UserDiagnosticAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_progress_id: int = Field(foreign_key="userprogress.id")
    question_id: int = Field(foreign_key="question.id")
    score: int
    answered_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
