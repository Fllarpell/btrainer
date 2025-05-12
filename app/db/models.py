from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLAlchemyEnum, Boolean, SmallInteger
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

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

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    language_code = Column(String(10), nullable=True)
    role = Column(SQLAlchemyEnum(UserRole, name="user_role_enum", create_type=False), default=UserRole.USER, nullable=False)
    subscription_status = Column(SQLAlchemyEnum(SubscriptionStatus, name="subscription_status_enum", create_type=False), default=SubscriptionStatus.NONE, nullable=False)
    trial_start_date = Column(DateTime(timezone=True), nullable=True)
    trial_end_date = Column(DateTime(timezone=True), nullable=True)
    is_blocked = Column(Boolean, default=False, nullable=False)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    solutions = relationship("Solution", back_populates="user")
    feedback = relationship("Feedback", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    admin_logs_initiated = relationship("AdminLog", foreign_keys="[AdminLog.admin_user_id]", back_populates="admin_user")

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    case_text = Column(Text, nullable=False)
    ai_model_used = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    solutions = relationship("Solution", back_populates="case")

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
    user = relationship("User", back_populates="solutions")

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
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    feedback_text = Column(Text, nullable=False)
    feedback_type = Column(SQLAlchemyEnum(FeedbackType, name="feedback_type_enum", create_type=False), default=FeedbackType.GENERAL, nullable=False)
    status = Column(SQLAlchemyEnum(FeedbackStatus, name="feedback_status_enum", create_type=False), default=FeedbackStatus.NEW, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="feedback")

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    yookassa_payment_id = Column(String, unique=True, index=True, nullable=True)
    telegram_payment_charge_id = Column(String, unique=True, index=True, nullable=True)
    plan_name = Column(String, nullable=True)
    amount = Column(Integer, nullable=False)
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

