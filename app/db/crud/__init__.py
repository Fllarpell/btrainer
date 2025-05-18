# This file makes Python treat the `crud` directory as a package. 

from .user_crud import (
    get_user_by_telegram_id, 
    get_user,
    create_user, 
    update_user_activity,
    grant_subscription_to_user,
    update_user_referral
)
from .case_crud import (
    create_case, 
    get_case,
    get_cases,
    # get_cases_by_user,
    # ... any other case related CRUD functions ...
)
from .solution_crud import (
    create_solution,
    get_solution,
    get_solutions_for_case,
    get_solutions_by_user,
    update_solution_ratings,
    count_solutions_by_user,
    count_solutions_by_user_and_rating
)
from .transaction_crud import (
    create_transaction,
    get_transaction_by_internal_id,
    get_transaction_by_yookassa_id,
    update_transaction_external_id,
    update_transaction_status_by_internal_id,
    update_transaction_status_by_id
)
from .feedback_crud import create_feedback

# You can also define __all__ if you want to control `from .crud import *` behavior
__all__ = [
    # User CRUD
    "get_user_by_telegram_id",
    "get_user",
    "create_user",
    "update_user_activity",
    "grant_subscription_to_user",
    "update_user_referral",
    # Case CRUD
    "create_case",
    "get_case",
    "get_cases",
    # "get_cases_by_user",
    # Solution CRUD
    "create_solution",
    "get_solution",
    "get_solutions_for_case",
    "get_solutions_by_user",
    "update_solution_ratings",
    "count_solutions_by_user",
    "count_solutions_by_user_and_rating",
    # Transaction CRUD
    "create_transaction",
    "get_transaction_by_internal_id",
    "get_transaction_by_yookassa_id",
    "update_transaction_external_id",
    "update_transaction_status_by_internal_id",
    "update_transaction_status_by_id",
    "create_feedback",
] 