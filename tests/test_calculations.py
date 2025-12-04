import math
from app import (
    monthly_loan_payment,
    remaining_loan_balance,
    lease_payment_from_mf,
    apr_to_money_factor,
)

def test_monthly_loan_payment_zero_interest():
    assert monthly_loan_payment(12000, 0, 12) == 1000

def test_monthly_loan_payment_positive():
    payment = monthly_loan_payment(20000, 5, 60)
    assert round(payment, 0) == 377  # standard expected payment

def test_remaining_loan_balance_reduces():
    bal_start = remaining_loan_balance(20000, 5, 60, 0)
    bal_12mo = remaining_loan_balance(20000, 5, 60, 12)
    assert bal_12mo < bal_start

def test_remaining_loan_balance_zero_after_term():
    bal = remaining_loan_balance(20000, 5, 60, 60)
    assert round(bal, 2) == 0.0

def test_money_factor_conversion():
    assert apr_to_money_factor(2.4) == 0.001  # standard formula APR/2400

def test_lease_payment_formula():
    cap_cost = 30000
    residual = 18000
    mf = 0.001
    payment = lease_payment_from_mf(cap_cost, residual, mf, 36)
    # depreciation = 12000/36 = 333.33; finance fee = (30000+18000)*0.001 = 48
    assert round(payment, 2) == round(333.33 + 48, 2)
