import math
from typing import List

import pandas as pd
import streamlit as st

from calc import (
    monthly_loan_payment,
    remaining_loan_balance,
    lease_payment_from_mf,
    apr_to_money_factor,
)

def linear_depreciation_value(initial_value: float,
                              end_value: float,
                              horizon_months: int,
                              month: int) -> float:
    """
    Simple linear depreciation: value moves from initial_value at month 0
    to end_value at month = horizon_months.
    """
    if horizon_months <= 0:
        return end_value
    month = max(0, month)
    slope = (end_value - initial_value) / horizon_months
    return initial_value + slope * min(month, horizon_months)


# ---------- Streamlit App ----------

def main():
    st.set_page_config(page_title="Lease vs Buy Calculator", layout="wide")
    st.title("🚗 Lease vs Buy Decision Helper")

    st.markdown(
        "This tool compares **leasing vs buying** a car over a chosen time horizon. "
        "It focuses on **net cost**: total cash out minus what you still own (equity). "
        "\n\nThis is an educational tool, not personalized financial advice."
    )

    # ----- Sidebar: Global Settings -----
    st.sidebar.header("Mode & Horizon")

    mode = st.sidebar.radio(
        "Select mode",
        ["Simple mode (recommended)", "Advanced mode"],
        index=0,
        help=(
            "**Simple mode**: you enter your monthly lease payment and basic loan info.\n"
            "**Advanced mode**: you control money factor, residual, cap cost, taxes, fees, etc."
        )
    )

    horizon_years = st.sidebar.slider("Comparison horizon (years)", 1, 7, 3)
    horizon_months = horizon_years * 12

    tax_rate_global = st.sidebar.number_input(
        "Sales tax rate (%)",
        min_value=0.0,
        value=6.25,
        step=0.25,
        format="%.2f",
        help="Approx combined state + local tax rate in your area."
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Tip: For lease comparisons, a **3-year horizon** often matches a 36-month lease."
    )

    is_advanced = mode == "Advanced mode"

    col_buy, col_lease = st.columns(2)

    # ---------- BUY INPUTS ----------
    with col_buy:
        st.subheader("🔹 Buying Scenario")

        if is_advanced:
            purchase_price = st.number_input(
                "Negotiated vehicle price (before tax) ($)",
                min_value=0.0,
                value=35000.0,
                step=500.0,
                format="%.2f",
            )

            buy_fees = st.number_input(
                "Upfront fees (doc, title, etc.) ($)",
                min_value=0.0,
                value=500.0,
                step=50.0,
                format="%.2f",
            )
        else:
            purchase_price = st.number_input(
                "Vehicle price (before tax) ($)",
                min_value=0.0,
                value=35000.0,
                step=500.0,
                format="%.2f",
                help="Rough price you’d pay for the car before tax."
            )
            # Keep it simple: bundle small fees into the price assumption
            buy_fees = 0.0

        down_payment_buy = st.number_input(
            "Down payment ($)",
            min_value=0.0,
            value=5000.0,
            step=500.0,
            format="%.2f",
        )

        loan_apr = st.number_input(
            "Loan APR (%)",
            min_value=0.0,
            value=5.0,
            step=0.25,
            format="%.2f",
        )

        loan_term_months = st.number_input(
            "Loan term (months)",
            min_value=12,
            max_value=96,
            value=60,
            step=12,
        )

        if is_advanced:
            expected_value_pct = st.slider(
                f"Expected car value at end of {horizon_years} years (% of purchase price)",
                min_value=10,
                max_value=80,
                value=55,
                step=1,
                help="Rough resale value as a percent of the original purchase price."
            )
        else:
            # Simple defaults based on horizon, editable via slider
            default_residual_by_horizon = {
                1: 80,
                2: 70,
                3: 60,
                4: 50,
                5: 45,
                6: 40,
                7: 35,
            }
            default_pct = default_residual_by_horizon.get(horizon_years, 50)
            expected_value_pct = st.slider(
                f"Estimated value at end of {horizon_years} years (% of purchase price)",
                min_value=10,
                max_value=80,
                value=default_pct,
                step=1,
                help="You can keep the default if you’re not sure."
            )

    # ---------- LEASE INPUTS ----------
    with col_lease:
        st.subheader("🔹 Lease Scenario")

        if is_advanced:
            msrp = st.number_input(
                "MSRP ($)",
                min_value=0.0,
                value=38000.0,
                step=500.0,
                format="%.2f",
            )

            cap_cost = st.number_input(
                "Negotiated cap cost / selling price for lease ($)",
                min_value=0.0,
                value=36000.0,
                step=500.0,
                format="%.2f",
            )
        else:
            # In simple mode, we don't need MSRP or cap cost for cost comparison
            msrp = None
            cap_cost = None

        lease_term_months = st.number_input(
            "Lease term (months)",
            min_value=12,
            max_value=60,
            value=36,
            step=6,
        )

        if is_advanced:
            residual_pct = st.slider(
                "Residual value at end of lease (% of MSRP)",
                min_value=30,
                max_value=80,
                value=58,
                step=1,
            )

            use_apr = st.checkbox("Use lease APR instead of money factor?", value=True)

            if use_apr:
                lease_apr = st.number_input(
                    "Lease APR (%)",
                    min_value=0.0,
                    value=3.0,
                    step=0.25,
                    format="%.2f",
                )
                money_factor = apr_to_money_factor(lease_apr)
            else:
                money_factor = st.number_input(
                    "Money factor",
                    min_value=0.0001,
                    value=0.00125,
                    step=0.00005,
                    format="%.5f",
                )

            lease_tax_rate = st.number_input(
                "Tax on lease payments (%)",
                min_value=0.0,
                value=tax_rate_global,
                step=0.25,
                format="%.2f",
                help="In many states, sales tax is charged on each lease payment."
            )

            drive_off = st.number_input(
                "Drive-off amount (cash due at signing) ($)",
                min_value=0.0,
                value=2000.0,
                step=250.0,
                format="%.2f",
            )
        else:
            # SIMPLE MODE: user enters final monthly payment with tax directly
            lease_monthly_with_tax = st.number_input(
                "Monthly lease payment (including tax) ($)",
                min_value=0.0,
                value=450.0,
                step=25.0,
                format="%.2f",
                help="Use the payment shown in your lease quote."
            )
            lease_tax_rate = 0.0  # already baked into the payment
            drive_off = st.number_input(
                "Drive-off / due at signing ($)",
                min_value=0.0,
                value=2000.0,
                step=250.0,
                format="%.2f",
            )
            residual_pct = None
            money_factor = None

        disposition_fee = st.number_input(
            "Disposition / turn-in fee at lease end ($)",
            min_value=0.0,
            value=395.0,
            step=25.0,
            format="%.2f",
        )

        allowed_miles_per_year = st.number_input(
            "Mileage allowance per year",
            min_value=5000,
            max_value=30000,
            value=12000,
            step=1000,
        )

        expected_miles_per_year = st.number_input(
            "Your expected miles per year",
            min_value=5000,
            max_value=50000,
            value=15000,
            step=1000,
        )

        excess_mileage_fee = st.number_input(
            "Excess mileage charge ($ per mile)",
            min_value=0.0,
            value=0.25,
            step=0.01,
            format="%.2f",
        )

    st.markdown("---")
    st.header("📊 Results & Comparison")

    # ---------- VALIDATION UTILITIES ----------

    def validate_positive(value, name):
        if value < 0:
            st.error(f"❌ {name} cannot be negative.")
            st.stop()

    def validate_percentage(value, name):
        if value < 0 or value > 100:
            st.error(f"❌ {name} must be between 0% and 100%.")
            st.stop()

    def validate_nonzero(value, name):
        if value == 0:
            st.error(f"❌ {name} cannot be zero.")
            st.stop()

    # Example validations for key inputs
    validate_positive(purchase_price, "Purchase price")
    validate_positive(down_payment_buy, "Down payment")
    validate_positive(loan_apr, "Loan APR")
    validate_nonzero(loan_term_months, "Loan term")
    validate_percentage(expected_value_pct, "Expected value %")

    if is_advanced:
        validate_positive(msrp, "MSRP")
        validate_positive(cap_cost, "Cap cost")
        validate_percentage(residual_pct, "Residual %")
        validate_positive(money_factor, "Money factor")

    validate_positive(lease_term_months, "Lease term")
    validate_positive(allowed_miles_per_year, "Mileage allowance")
    validate_positive(lease_monthly_with_tax, "Lease payment")


    
    # ---------- BUY CALCULATIONS ----------

    taxable_amount = purchase_price + buy_fees
    total_tax = taxable_amount * (tax_rate_global / 100)
    total_purchase_cost = taxable_amount + total_tax

    loan_amount = max(total_purchase_cost - down_payment_buy, 0.0)
    buy_monthly_payment = monthly_loan_payment(loan_amount, loan_apr, loan_term_months)

    # Expected value at end of horizon
    end_value_at_horizon = purchase_price * (expected_value_pct / 100)

    # ---------- LEASE CALCULATIONS ----------

    if is_advanced:
        residual_value = msrp * (residual_pct / 100)
        base_lease_monthly = lease_payment_from_mf(cap_cost, residual_value, money_factor, lease_term_months)
        lease_monthly_with_tax = base_lease_monthly * (1 + lease_tax_rate / 100)
    # else: lease_monthly_with_tax already provided by user in simple mode

    lease_years = lease_term_months / 12
    total_allowed_miles = allowed_miles_per_year * lease_years
    total_expected_miles = expected_miles_per_year * lease_years
    excess_miles = max(0.0, total_expected_miles - total_allowed_miles)
    mileage_penalty = excess_miles * excess_mileage_fee

    total_lease_payments_term = lease_monthly_with_tax * lease_term_months
    net_cost_lease_full_term = drive_off + total_lease_payments_term + mileage_penalty + disposition_fee

    # ---------- COST OVER TIME (FOR PLOTS) ----------

    months = list(range(1, horizon_months + 1))
    buy_net_cost_by_month: List[float] = []
    lease_net_cost_by_month: List[float] = []

    for m in months:
        # Buying: net cost = down + payments made + remaining balance − estimated car value
        payments_made = buy_monthly_payment * min(m, loan_term_months)
        remaining_bal = remaining_loan_balance(loan_amount, loan_apr, loan_term_months, m)
        value_m = linear_depreciation_value(purchase_price, end_value_at_horizon, horizon_months, m)
        net_cost_buy_m = down_payment_buy + payments_made + remaining_bal - value_m
        buy_net_cost_by_month.append(net_cost_buy_m)

        # Leasing: cumulative cash out
        if m <= lease_term_months:
            lease_cost_m = drive_off + lease_monthly_with_tax * m
            if m == lease_term_months:
                lease_cost_m += mileage_penalty + disposition_fee
        else:
            # After lease ends, cost is flat at full lease net cost
            lease_cost_m = net_cost_lease_full_term

        lease_net_cost_by_month.append(lease_cost_m)

    # Net cost at chosen horizon (last month)
    net_cost_buy = buy_net_cost_by_month[-1]
    net_cost_lease_at_horizon = lease_net_cost_by_month[-1]

    # ---------- DISPLAY SUMMARY METRICS ----------

    col_res_buy, col_res_lease = st.columns(2)

    with col_res_buy:
        st.subheader("Buying Summary")
        st.metric("Monthly payment", f"${buy_monthly_payment:,.0f}")
        st.write(f"Total purchase cost (price + fees + tax): "
                 f"**${total_purchase_cost:,.0f}**")
        st.write(f"Loan amount financed: **${loan_amount:,.0f}**")
        st.write(f"Estimated car value at end of {horizon_years} years: "
                 f"**${end_value_at_horizon:,.0f}**")
        st.write(
            f"**Net cost over {horizon_years} years** "
            f"(cash out − equity): `~${net_cost_buy:,.0f}`"
        )

    with col_res_lease:
        st.subheader("Leasing Summary")
        st.metric("Monthly payment"
                  f"{' (with tax)' if is_advanced else ''}",
                  f"${lease_monthly_with_tax:,.0f}")
        st.write(f"Drive-off (due at signing): **${drive_off:,.0f}**")
        st.write(
            f"Lease payments over {lease_term_months} months"
            f"{' (with tax)' if is_advanced else ''}: "
            f"**${total_lease_payments_term:,.0f}**"
        )
        if mileage_penalty > 0:
            st.write(f"Estimated mileage penalties at lease end: "
                     f"**${mileage_penalty:,.0f}**")
        st.write(f"Disposition / turn-in fee at lease end: **${disposition_fee:,.0f}**")
        st.write(f"**Total net cost for one full lease**: "
                 f"`~${net_cost_lease_full_term:,.0f}`")
        st.write(
            f"**Net cost at {horizon_years} years** "
            f"(same lease assumptions): `~${net_cost_lease_at_horizon:,.0f}`"
        )

    st.markdown("---")

    # ---------- RECOMMENDATION ----------

    diff = net_cost_buy - net_cost_lease_at_horizon

    if diff > 0:
        st.success(
            f"✅ **Leasing is cheaper by approximately ${abs(diff):,.0f} "
            f"over {horizon_years} years** under these assumptions."
        )
    elif diff < 0:
        st.success(
            f"✅ **Buying is cheaper by approximately ${abs(diff):,.0f} "
            f"over {horizon_years} years** under these assumptions."
        )
    else:
        st.info("Both options have roughly the same net cost with these inputs.")

    st.caption(
        "Net cost = all cash you send out (down payment, payments, fees, penalties) "
        "minus what you effectively own at the end (equity in the car if you buy)."
    )

    # ---------- VISUALIZATIONS ----------

    st.markdown("## 📈 Net Cost Over Time (Month by Month)")

    df_time = pd.DataFrame(
        {
            "Month": months,
            "Buy (net cost)": buy_net_cost_by_month,
            "Lease (net cost)": lease_net_cost_by_month,
        }
    ).set_index("Month")

    st.line_chart(df_time)

    st.markdown("## 📊 Total Net Cost at Your Selected Horizon")

    df_bar = pd.DataFrame(
        {
            "Option": ["Buy", "Lease"],
            "Net cost": [net_cost_buy, net_cost_lease_at_horizon],
        }
    ).set_index("Option")

    st.bar_chart(df_bar)

    st.caption(
        "The line chart shows how your position changes over time.\n"
        "The bar chart shows the final comparison at the horizon you chose."
    )


if __name__ == '__main__':
    main()
