from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum, Boolean, SmallInteger, BigInteger, Numeric, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column, declarative_base
from sqlalchemy.sql import func
import enum
from typing import List, Optional
from datetime import datetime

Base = declarative_base()

class AISourceType(str, enum.Enum):
    URL = "url"
    BOOK = "book"
    ARTICLE = "article"
    MANUAL = "manual"
    RESEARCH_PAPER = "research_paper"
    FORUM_POST = "forum_post"
    OTHER = "other"

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class SubscriptionStatus(str, enum.Enum):
    NONE = "none"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_premium: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLAlchemyEnum(UserRole, name="user_role_enum", create_type=False), default=UserRole.USER, nullable=False)
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(SQLAlchemyEnum(SubscriptionStatus, name="subscription_status_enum", create_type=False), default=SubscriptionStatus.NONE, nullable=False)
    current_plan_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    db_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    converted_from_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default='false')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    current_case_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    solutions: Mapped[List["Solution"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    feedbacks: Mapped[List["Feedback"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    admin_logs_initiated: Mapped[List["AdminLog"]] = relationship("AdminLog", foreign_keys="[AdminLog.admin_user_id]", back_populates="admin_user")
    created_cases: Mapped[List["Case"]] = relationship(back_populates="created_by_user", foreign_keys="Case.created_by_user_id", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=True)
    case_text = Column(Text, nullable=False)
    ai_model_used = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    solutions = relationship("Solution", back_populates="case")
    created_by_user: Mapped[Optional["User"]] = relationship(back_populates="created_cases", foreign_keys=[created_by_user_id])

class Solution(Base):
    __tablename__ = "solutions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    solution_text = Column(Text, nullable=False)
    ai_analysis_text = Column(Text, nullable=True)
    user_rating_of_case = Column(SmallInteger, nullable=True)
    user_rating_of_analysis = Column(SmallInteger, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="solutions")
    user: Mapped["User"] = relationship(back_populates="solutions")

class FeedbackType(str, enum.Enum):
    BUG = "bug_report"
    FEATURE = "feature_request"
    GENERAL = "general_comment"

class FeedbackStatus(str, enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # AI analysis fields
    is_meaningful_ai: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ai_analysis_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # Reason from AI for meaningfulness decision
    ai_analysis_category: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Category from AI (e.g., bug_report, feature_request)
    raw_ai_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True) # Store raw JSON response from AI, just in case

    user: Mapped["User"] = relationship(back_populates="feedbacks")

    def __repr__(self):
        return f"<Feedback(id={self.id}, user_id={self.user_id}, submitted_at={self.submitted_at}, meaningful_ai={self.is_meaningful_ai})>"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    internal_transaction_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    yookassa_payment_id = Column(String, unique=True, index=True, nullable=True)
    telegram_payment_charge_id = Column(String, unique=True, index=True, nullable=True)
    plan_name = Column(String, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(SQLAlchemyEnum(TransactionStatus, name="transaction_status_enum", create_type=False), default=TransactionStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="transactions")

class AdminAction(str, enum.Enum):
    USER_BLOCK = "user_block"
    USER_UNBLOCK = "user_unblock"
    ROLE_CHANGE = "role_change"
    SUBSCRIPTION_CHANGE = "subscription_change"
    MANUAL_PAYMENT_RECORD = "manual_payment_record"
    TRIAL_GRANTED = "trial_granted"
    TRIAL_CANCELLED = "trial_cancelled"
    SUBSCRIPTION_ACTIVATED = "subscription_activated"
    SUBSCRIPTION_DEACTIVATED = "subscription_deactivated"
    OTHER = "other"

class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(SQLAlchemyEnum(AdminAction, name="admin_action_enum", create_type=False), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    admin_user = relationship("User", foreign_keys=[admin_user_id], back_populates="admin_logs_initiated")
    target_user = relationship("User", foreign_keys=[target_user_id])

class AIReference(Base):
    __tablename__ = "ai_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[AISourceType] = mapped_column(SQLAlchemyEnum(AISourceType, name="ai_source_type_enum", create_type=False), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False) # e.g., Book title, Article name, URL description
    url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True) # For URLs
    citation_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # E.g., page numbers, authors for books/articles not in description
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<AIReference(id={self.id}, type='{self.source_type.value}', description='{self.description[:50]}...', active={self.is_active})>"

