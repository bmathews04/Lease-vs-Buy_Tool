def monthly_loan_payment(loan_amount: float, apr_percent: float, term_months: int) -> float:
    if term_months <= 0 or loan_amount <= 0:
        return 0.0
    r = apr_percent / 100 / 12
    if r == 0:
        return loan_amount / term_months
    return loan_amount * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)


def remaining_loan_balance(loan_amount: float, apr_percent: float, term_months: int, months_elapsed: int) -> float:
    months_elapsed = max(0, min(months_elapsed, term_months))
    if term_months <= 0 or loan_amount <= 0:
        return 0.0
    r = apr_percent / 100 / 12
    payment = monthly_loan_payment(loan_amount, apr_percent, term_months)
    if r == 0:
        return max(0.0, loan_amount - payment * months_elapsed)
    factor = (1 + r) ** months_elapsed
    balance = loan_amount * factor - payment * (factor - 1) / r
    return max(0.0, balance)


def lease_payment_from_mf(cap_cost: float, residual_value: float, money_factor: float, term_months: int) -> float:
    if term_months <= 0 or cap_cost <= 0:
        return 0.0
    depreciation_fee = (cap_cost - residual_value) / term_months
    finance_fee = (cap_cost + residual_value) * money_factor
    return depreciation_fee + finance_fee


def apr_to_money_factor(apr_percent: float) -> float:
    return apr_percent / 2400
