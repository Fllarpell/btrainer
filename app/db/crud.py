from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_
from typing import List, Optional, Type
import datetime

from .models import Base, User, Case, Solution, Feedback, Transaction, AdminLog, UserRole, SubscriptionStatus, FeedbackType, FeedbackStatus, TransactionStatus, AdminAction


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)

def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    return db.execute(select(User).filter(User.telegram_id == telegram_id)).scalar_one_or_none()

def create_user(
    db: Session, 
    telegram_id: int, 
    username: Optional[str] = None, 
    first_name: Optional[str] = None, 
    last_name: Optional[str] = None, 
    language_code: Optional[str] = None,
    role: UserRole = UserRole.USER,
    subscription_status: SubscriptionStatus = SubscriptionStatus.NONE,
    trial_start_date: Optional[datetime.datetime] = None,
    trial_end_date: Optional[datetime.datetime] = None
) -> User:
    db_user = User(
        telegram_id=telegram_id, 
        username=username, 
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        role=role,
        subscription_status=subscription_status,
        trial_start_date=trial_start_date,
        trial_end_date=trial_end_date,
        last_active_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(db_user)
    db.flush() # Чтобы получить db_user.id, если он автогенерируемый и нужен сразу
    # db.commit() # Коммит обычно делается на более высоком уровне (например, после выполнения запроса)
    # db.refresh(db_user) # Обновить объект из БД, если нужно (после коммита)
    return db_user

def update_user_activity(db: Session, telegram_id: int) -> Optional[User]:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.last_active_at = datetime.datetime.now(datetime.timezone.utc)
        # db.commit()
        # db.refresh(db_user)
    return db_user

def set_user_subscription(
    db: Session, 
    telegram_id: int, 
    status: SubscriptionStatus, 
    trial_start: Optional[datetime.datetime] = None,
    trial_end: Optional[datetime.datetime] = None,
    plan_name: Optional[str] = None
) -> Optional[User]:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.subscription_status = status
        if status == SubscriptionStatus.TRIAL:
            db_user.trial_start_date = trial_start if trial_start else datetime.datetime.now(datetime.timezone.utc)
            db_user.trial_end_date = trial_end
        elif status == SubscriptionStatus.ACTIVE:
            db_user.trial_start_date = None 
            db_user.trial_end_date = None
        # db.commit()
        # db.refresh(db_user)
    return db_user

def set_user_role(db: Session, telegram_id: int, role: UserRole) -> Optional[User]:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.role = role
        # db.commit()
        # db.refresh(db_user)
    return db_user

def block_user(db: Session, telegram_id: int) -> Optional[User]:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.is_blocked = True
        # db.commit()
        # db.refresh(db_user)
    return db_user

def unblock_user(db: Session, telegram_id: int) -> Optional[User]:
    db_user = get_user_by_telegram_id(db, telegram_id)
    if db_user:
        db_user.is_blocked = False
        # db.commit()
        # db.refresh(db_user)
    return db_user

def get_users_by_role(db: Session, role: UserRole, skip: int = 0, limit: int = 100) -> List[User]:
    return db.execute(select(User).filter(User.role == role).offset(skip).limit(limit)).scalars().all()


def create_case(db: Session, title: str, case_text: str, ai_model_used: Optional[str] = None, prompt_version: Optional[str] = None) -> Case:
    db_case = Case(
        title=title, 
        case_text=case_text, 
        ai_model_used=ai_model_used,
        prompt_version=prompt_version
    )
    db.add(db_case)
    db.flush()
    return db_case

def get_case(db: Session, case_id: int) -> Optional[Case]:
    return db.get(Case, case_id)

def get_cases(db: Session, skip: int = 0, limit: int = 100) -> List[Case]:
    return db.execute(select(Case).order_by(Case.id.desc()).offset(skip).limit(limit)).scalars().all()

def get_random_case(db: Session) -> Optional[Case]:
    return db.execute(select(Case).order_by(func.random())).scalars().first()


def create_solution(
    db: Session, 
    case_id: int, 
    user_id: int, 
    solution_text: str, 
    ai_analysis_text: Optional[str] = None
) -> Solution:

    
    db_solution = Solution(
        case_id=case_id, 
        user_id=user_id,
        solution_text=solution_text, 
        ai_analysis_text=ai_analysis_text
    )
    db.add(db_solution)
    db.flush()
    return db_solution

def get_solution(db: Session, solution_id: int) -> Optional[Solution]:
    return db.get(Solution, solution_id)

def get_solutions_for_case(db: Session, case_id: int, skip: int = 0, limit: int = 100) -> List[Solution]:
    return db.execute(
        select(Solution).filter(Solution.case_id == case_id).order_by(Solution.submitted_at.desc()).offset(skip).limit(limit)
    ).scalars().all()

def get_solutions_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Solution]:
    return db.execute(
        select(Solution).filter(Solution.user_id == user_id).order_by(Solution.submitted_at.desc()).offset(skip).limit(limit)
    ).scalars().all()

def update_solution_ratings(
    db: Session, 
    solution_id: int, 
    user_rating_of_case: Optional[int] = None, 
    user_rating_of_analysis: Optional[int] = None
) -> Optional[Solution]:
    db_solution = get_solution(db, solution_id)
    if db_solution:
        if user_rating_of_case is not None:
            db_solution.user_rating_of_case = user_rating_of_case
        if user_rating_of_analysis is not None:
            db_solution.user_rating_of_analysis = user_rating_of_analysis
        # db.commit()
        # db.refresh(db_solution)
    return db_solution


def create_feedback(
    db: Session, 
    user_id: int,
    feedback_text: str, 
    feedback_type: FeedbackType = FeedbackType.GENERAL,
    initial_status: FeedbackStatus = FeedbackStatus.NEW
) -> Feedback:
    db_feedback = Feedback(
        user_id=user_id,
        feedback_text=feedback_text,
        feedback_type=feedback_type,
        status=initial_status
    )
    db.add(db_feedback)
    db.flush()
    return db_feedback

def get_feedback(db: Session, feedback_id: int) -> Optional[Feedback]:
    return db.get(Feedback, feedback_id)

def get_feedback_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Feedback]:
    return db.execute(
        select(Feedback).filter(Feedback.user_id == user_id).order_by(Feedback.submitted_at.desc()).offset(skip).limit(limit)
    ).scalars().all()

def get_all_feedback(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    status_filter: Optional[FeedbackStatus] = None
) -> List[Feedback]:
    query = select(Feedback).order_by(Feedback.submitted_at.desc())
    if status_filter:
        query = query.filter(Feedback.status == status_filter)
    return db.execute(query.offset(skip).limit(limit)).scalars().all()

def update_feedback_status(db: Session, feedback_id: int, status: FeedbackStatus) -> Optional[Feedback]:
    db_feedback = get_feedback(db, feedback_id)
    if db_feedback:
        db_feedback.status = status
        db_feedback.updated_at = datetime.datetime.now(datetime.timezone.utc)
        # db.commit()
        # db.refresh(db_feedback)
    return db_feedback


def create_transaction(
    db: Session,
    user_id: int,
    amount: int,
    currency: str,
    status: TransactionStatus = TransactionStatus.PENDING,
    plan_name: Optional[str] = None,
    yookassa_payment_id: Optional[str] = None,
    telegram_payment_charge_id: Optional[str] = None
) -> Transaction:
    db_transaction = Transaction(
        user_id=user_id,
        amount=amount,
        currency=currency,
        status=status,
        plan_name=plan_name,
        yookassa_payment_id=yookassa_payment_id,
        telegram_payment_charge_id=telegram_payment_charge_id
    )
    db.add(db_transaction)
    db.flush()
    return db_transaction

def get_transaction(db: Session, transaction_id: int) -> Optional[Transaction]:
    return db.get(Transaction, transaction_id)

def get_transaction_by_yookassa_id(db: Session, yookassa_payment_id: str) -> Optional[Transaction]:
    return db.execute(
        select(Transaction).filter(Transaction.yookassa_payment_id == yookassa_payment_id)
    ).scalar_one_or_none()

def get_transactions_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[Transaction]:
    return db.execute(
        select(Transaction).filter(Transaction.user_id == user_id).order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    ).scalars().all()

def update_transaction(
    db: Session, 
    new_status: TransactionStatus,
    transaction_id: Optional[int] = None, 
    yookassa_payment_id_to_find: Optional[str] = None,

    new_yookassa_payment_id: Optional[str] = None,
    new_telegram_payment_charge_id: Optional[str] = None
) -> Optional[Transaction]:
    db_transaction = None
    if transaction_id:
        db_transaction = get_transaction(db, transaction_id)
    elif yookassa_payment_id_to_find:
        db_transaction = get_transaction_by_yookassa_id(db, yookassa_payment_id_to_find)
    
    if db_transaction:
        db_transaction.status = new_status
        if new_yookassa_payment_id:
            db_transaction.yookassa_payment_id = new_yookassa_payment_id
        if new_telegram_payment_charge_id:
            db_transaction.telegram_payment_charge_id = new_telegram_payment_charge_id
        db_transaction.updated_at = datetime.datetime.now(datetime.timezone.utc)
    return db_transaction


def create_admin_log(
    db: Session,
    admin_user_id: int,
    action: AdminAction,
    target_user_id: Optional[int] = None,
    details: Optional[str] = None
) -> AdminLog:
    db_log = AdminLog(
        admin_user_id=admin_user_id,
        action=action,
        target_user_id=target_user_id,
        details=details
    )
    db.add(db_log)
    db.flush()
    return db_log

def get_admin_logs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    admin_user_id_filter: Optional[int] = None,
    target_user_id_filter: Optional[int] = None,
    action_filter: Optional[AdminAction] = None
) -> List[AdminLog]:
    query = select(AdminLog).order_by(AdminLog.timestamp.desc())
    if admin_user_id_filter:
        query = query.filter(AdminLog.admin_user_id == admin_user_id_filter)
    if target_user_id_filter:
        query = query.filter(AdminLog.target_user_id == target_user_id_filter)
    if action_filter:
        query = query.filter(AdminLog.action == action_filter)
    
    return db.execute(query.offset(skip).limit(limit)).scalars().all() 