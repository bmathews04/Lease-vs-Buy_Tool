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


# ---------- Helper: simple linear depreciation ----------

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


# ---------- Validation utilities ----------

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


# ---------- Confidence helper ----------

def get_confidence_label(mode: str, using_estimates: bool) -> str:
    if mode == "Simple mode (recommended)":
        return (
            "Medium – based on your monthly payment and typical assumptions. "
            "Very useful for comparisons, but exact dealer math may differ slightly."
        )
    if not using_estimates:
        return (
            "High – based on dealer’s actual money factor, residual, and cap cost."
        )
    return (
        "Medium – some lease inputs (like residual or money factor) are using "
        "typical market estimates because the dealer didn’t provide them."
    )


# ---------- Loan amortization helper ----------

def build_amortization_schedule(loan_amount: float,
                                apr_percent: float,
                                term_months: int,
                                monthly_payment: float) -> pd.DataFrame:
    """Return a DataFrame with amortization details by month."""
    rows = []
    balance = loan_amount
    r = apr_percent / 100 / 12 if term_months > 0 else 0.0

    for m in range(1, term_months + 1):
        if r > 0:
            interest = balance * r
        else:
            interest = 0.0
        principal = monthly_payment - interest
        if principal < 0:
            principal = 0.0
        new_balance = max(0.0, balance - principal)
        rows.append(
            {
                "Month": m,
                "Payment": monthly_payment,
                "Principal": principal,
                "Interest": interest,
                "Remaining balance": new_balance,
            }
        )
        balance = new_balance

    return pd.DataFrame(rows)


# ---------- Lease cashflow helper ----------

def build_lease_cashflows(lease_term_months: int,
                          drive_off: float,
                          lease_monthly_with_tax: float,
                          mileage_penalty: float,
                          disposition_fee: float) -> pd.DataFrame:
    """Return a DataFrame with lease cashflows over time."""
    rows = []
    cumulative = 0.0

    # Month 0 – drive-off
    cumulative += drive_off
    rows.append(
        {
            "Step": "Start",
            "Month": 0,
            "Type": "Drive-off",
            "Cash flow": drive_off,
            "Cumulative": cumulative,
        }
    )

    # Monthly payments
    for m in range(1, lease_term_months + 1):
        cf = lease_monthly_with_tax
        cumulative += cf
        rows.append(
            {
                "Step": f"Month {m}",
                "Month": m,
                "Type": "Monthly payment",
                "Cash flow": cf,
                "Cumulative": cumulative,
            }
        )

    # End-of-lease charges
    if mileage_penalty > 0:
        cumulative += mileage_penalty
        rows.append(
            {
                "Step": "End of lease – mileage penalty",
                "Month": lease_term_months,
                "Type": "Mileage penalty",
                "Cash flow": mileage_penalty,
                "Cumulative": cumulative,
            }
        )

    if disposition_fee > 0:
        cumulative += disposition_fee
        rows.append(
            {
                "Step": "End of lease – disposition fee",
                "Month": lease_term_months,
                "Type": "Disposition fee",
                "Cash flow": disposition_fee,
                "Cumulative": cumulative,
            }
        )

    return pd.DataFrame(rows)


# ---------- Streamlit App ----------

def main():
    st.set_page_config(page_title="Lease vs Buy Calculator", layout="wide")
    st.title("🚗 Lease vs Buy Decision Helper")

    st.markdown(
        "This tool compares **leasing vs buying** a car over a chosen time horizon.\n\n"
        "- In **Simple mode**, you only need the numbers the dealer almost always gives you.\n"
        "- In **Advanced mode**, you can plug in (or estimate) the full lease structure."
        "\n\nThis is an educational tool, not personalized financial advice."
    )

    # ----- Sidebar: Global Settings -----
    st.sidebar.header("Mode & Horizon")

    mode = st.sidebar.radio(
        "Select mode",
        ["Simple mode (recommended)", "Advanced mode"],
        index=0,
        help=(
            "**Simple mode**: just use your monthly lease payment and basic loan info.\n"
            "**Advanced mode**: enter (or estimate) money factor, residual, cap cost, etc."
        ),
    )

    horizon_years = st.sidebar.slider("Comparison horizon (years)", 1, 7, 3)
    horizon_months = horizon_years * 12

    tax_rate_global = st.sidebar.number_input(
        "Sales tax rate on vehicle purchase (%)",
        min_value=0.0,
        value=6.25,
        step=0.25,
        format="%.2f",
        help="Approx combined state + local tax rate in your area for **buying**.",
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

        purchase_price = st.number_input(
            "Vehicle price (before tax) ($)",
            min_value=0.0,
            value=35000.0,
            step=500.0,
            format="%.2f",
            help="Rough price you’d pay for the car before tax.",
        )

        if is_advanced:
            buy_fees = st.number_input(
                "Upfront fees (doc, title, etc.) ($)",
                min_value=0.0,
                value=500.0,
                step=50.0,
                format="%.2f",
            )
        else:
            # In simple mode, keep it light: bundle minor fees into price
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

        # Expected value slider with sensible defaults by horizon
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
            f"Estimated value at end of {horizon_years} years "
            "(% of purchase price)",
            min_value=10,
            max_value=80,
            value=default_pct,
            step=1,
            help=(
                "If you’re not sure, the default is a typical resale range for that age. "
                "You can adjust if you expect unusually high or low resale value."
            ),
        )

    # ---------- LEASE INPUTS ----------
    with col_lease:
        st.subheader("🔹 Lease Scenario")

        lease_term_months = st.number_input(
            "Lease term (months)",
            min_value=12,
            max_value=60,
            value=36,
            step=6,
        )

        # Flag for whether user is relying on estimates (for confidence label)
        using_estimates = False

        if is_advanced:
            st.markdown("**Advanced lease structure**")

            msrp = st.number_input(
                "MSRP ($)",
                min_value=0.0,
                value=38000.0,
                step=500.0,
                format="%.2f",
                help="The sticker price on the window. Used for residual calculations.",
            )

            # Cap cost: either user-entered or estimated from MSRP
            estimate_cap_cost = st.checkbox(
                "Dealer didn't give cap cost? Estimate ~7% discount off MSRP",
                value=True,
            )

            if estimate_cap_cost and msrp > 0:
                cap_cost = round(msrp * 0.93, 2)
                st.info(
                    f"Estimated cap cost based on typical ~7% discount: "
                    f"**${cap_cost:,.0f}**"
                )
                using_estimates = True
            else:
                cap_cost = st.number_input(
                    "Negotiated cap cost / selling price for lease ($)",
                    min_value=0.0,
                    value=36000.0,
                    step=500.0,
                    format="%.2f",
                    help="Ask the dealer for the 'cap cost' or 'agreed upon value.'",
                )

            # Residual and MF – often *not* given by dealers
            residual_pct = st.slider(
                "Residual value at end of lease (% of MSRP)",
                min_value=30,
                max_value=80,
                value=58,
                step=1,
                help=(
                    "The bank’s guess of what the car is worth at lease end. "
                    "If your dealer didn’t tell you, leaving the default is usually fine "
                    "for a typical 3-year lease."
                ),
            )

            lease_tax_rate = st.number_input(
                "Tax on lease payments (%)",
                min_value=0.0,
                value=tax_rate_global,
                step=0.25,
                format="%.2f",
                help="Many states tax each lease payment rather than the full price.",
            )

            drive_off = st.number_input(
                "Drive-off amount (cash due at signing) ($)",
                min_value=0.0,
                value=2000.0,
                step=250.0,
                format="%.2f",
                help="Everything you pay upfront: first month, fees, etc.",
            )

            # --- Money factor selection / estimation ---
            use_estimated_mf = st.checkbox(
                "Dealer didn't share money factor? Use a typical value",
                value=True,
            )

            if use_estimated_mf:
                # Typical MF ≈ 0.00125 (~3% APR)
                money_factor = 0.00125
                st.info(
                    "Using typical money factor **0.00125** "
                    "(≈ 3.0% APR). Adjust in advanced scenarios or use the "
                    "reverse-engineer tool below."
                )
                using_estimates = True
            else:
                money_factor = st.number_input(
                    "Money factor",
                    min_value=0.0001,
                    value=0.00125,
                    step=0.00005,
                    format="%.5f",
                    help=(
                        "Lease equivalent of an interest rate. "
                        "You may see it as a small decimal like 0.00125."
                    ),
                )

            # --- Reverse-engineer MF from a quoted payment (optional) ---
            with st.expander("🔍 Reverse-engineer money factor from a quoted payment"):
                st.caption(
                    "If your dealer gave you a monthly payment but not the money factor, "
                    "you can estimate the implied MF here."
                )
                known_payment_with_tax = st.number_input(
                    "Quoted monthly payment from dealer (with tax) ($)",
                    min_value=0.0,
                    value=0.0,
                    step=10.0,
                    format="%.2f",
                )

                if known_payment_with_tax > 0 and msrp > 0 and cap_cost > 0:
                    # Convert to pre-tax payment (if tax is nonzero)
                    if lease_tax_rate > 0:
                        payment_pre_tax = known_payment_with_tax / (
                            1 + lease_tax_rate / 100
                        )
                    else:
                        payment_pre_tax = known_payment_with_tax

                    residual_value = msrp * (residual_pct / 100)
                    denom = cap_cost + residual_value
                    dep_fee = (cap_cost - residual_value) / lease_term_months

                    if denom > 0:
                        mf_implied = (payment_pre_tax - dep_fee) / denom
                        if mf_implied > 0:
                            money_factor = mf_implied
                            using_estimates = True
                            implied_apr = mf_implied * 2400
                            st.success(
                                f"Estimated money factor from this payment: "
                                f"**{mf_implied:.5f}** "
                                f"(≈ **{implied_apr:.2f}% APR**). "
                                "This value will be used in the comparison below."
                            )
                        else:
                            st.warning(
                                "The inputs result in a non-positive money factor. "
                                "Double-check the payment, term, and cap cost values."
                            )
                    else:
                        st.warning(
                            "Cap cost + residual is zero, so the implied money factor "
                            "cannot be calculated. Check MSRP / cap cost."
                        )

            lease_monthly_with_tax = None  # computed below

        else:
            # SIMPLE MODE: only ask for what users actually see on the quote
            st.markdown(
                "You only need the numbers that are almost always on a dealer quote."
            )

            lease_monthly_with_tax = st.number_input(
                "Monthly lease payment (including tax) ($)",
                min_value=0.0,
                value=450.0,
                step=25.0,
                format="%.2f",
                help="Use the payment shown on the dealer’s sheet, with tax included.",
            )

            drive_off = st.number_input(
                "Drive-off / due at signing ($)",
                min_value=0.0,
                value=2000.0,
                step=250.0,
                format="%.2f",
            )

            lease_tax_rate = 0.0  # already baked into the payment
            residual_pct = None
            money_factor = None
            msrp = None
            cap_cost = None

        disposition_fee = st.number_input(
            "Disposition / turn-in fee at lease end ($)",
            min_value=0.0,
            value=395.0,
            step=25.0,
            format="%.2f",
            help="If you don't know, $350–$495 is common. Leaving the default is fine.",
        )

        allowed_miles_per_year = st.number_input(
            "Mileage allowance per year",
            min_value=5000,
            max_value=30000,
            value=12000,
            step=1000,
            help="Typically 10k, 12k, or 15k. Check your quote.",
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
            help="If you don’t know, $0.20–$0.30 is common. Default is a safe estimate.",
        )

    # ---------- Dealer Checklist (Tabs) ----------

    st.markdown("### 📝 What to ask your dealer")

    st.caption(
        "Use this checklist when you’re talking to the dealer. "
        "Tick items off as you collect them."
    )

    tab_buy, tab_lease, tab_tips = st.tabs(
        ["Buying quote checklist", "Lease quote checklist", "General tips"]
    )

    with tab_buy:
        st.markdown("**Key items for a purchase quote:**")
        st.checkbox("Final **out-the-door price** (including all fees & taxes)")
        st.checkbox("Breakdown of **doc, title, registration, and other fees**")
        st.checkbox("**Purchase price** of the car (before fees & tax)")
        st.checkbox("**Rebates or incentives** applied")
        st.checkbox("Loan **APR** and whether it’s promotional / conditional")
        st.checkbox("Loan **term in months**")
        st.checkbox("Any required **down payment**")
        st.checkbox("Whether the loan has **prepayment penalties**")

    with tab_lease:
        st.markdown("**Key items for a lease quote:**")
        st.checkbox("**MSRP** (sticker price)")
        st.checkbox("**Cap cost / selling price** used for the lease")
        st.checkbox("Any **cap cost reduction** (down payment, rebates applied)")
        st.checkbox("Lease **term in months**")
        st.checkbox("Monthly payment **before tax** and **with tax**")
        st.checkbox("**Money factor (MF)** or equivalent APR")
        st.checkbox("**Residual value %** (percentage of MSRP)")
        st.checkbox("Total **drive-off / due at signing** amount")
        st.checkbox("Annual **mileage allowance**")
        st.checkbox("**Excess mileage charge** ($ per mile)")
        st.checkbox("Lease **acquisition fee** (if any)")
        st.checkbox("Lease **disposition / turn-in fee** at the end")

    with tab_tips:
        st.markdown("**General tips when talking to the dealer:**")
        st.markdown(
            "- Ask for everything in **writing** (PDF or email quote).\n"
            "- Clarify whether numbers shown are **before or after tax**.\n"
            "- Confirm whether the quote assumes any **trade-in** or **rebate**.\n"
            "- If something isn’t clear (like money factor or residual), "
            "ask: _“Can you please show the money factor and residual used "
            "to calculate this payment?”_\n"
            "- Don’t be afraid to say you’re using a **calculator** to compare "
            "lease vs buy – it shows you’re informed, not difficult."
        )

    st.markdown("---")
    st.header("📊 Results & Comparison")

    # ---------- VALIDATIONS ----------

    validate_positive(purchase_price, "Purchase price")
    validate_positive(down_payment_buy, "Down payment")
    validate_positive(loan_apr, "Loan APR")
    validate_nonzero(loan_term_months, "Loan term")
    validate_percentage(expected_value_pct, "Estimated value %")

    validate_positive(lease_term_months, "Lease term")
    validate_positive(allowed_miles_per_year, "Mileage allowance")
    validate_positive(excess_mileage_fee, "Excess mileage fee")
    validate_positive(disposition_fee, "Disposition fee")

    if is_advanced:
        validate_positive(msrp, "MSRP")
        validate_positive(cap_cost, "Cap cost")
        validate_percentage(residual_pct, "Residual %")
        validate_positive(money_factor, "Money factor")
    else:
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
        base_lease_monthly = lease_payment_from_mf(
            cap_cost, residual_value, money_factor, lease_term_months
        )
        lease_monthly_with_tax = base_lease_monthly * (1 + lease_tax_rate / 100)
    # else: lease_monthly_with_tax already provided by user in simple mode

    lease_years = lease_term_months / 12
    total_allowed_miles = allowed_miles_per_year * lease_years
    total_expected_miles = expected_miles_per_year * lease_years
    excess_miles = max(0.0, total_expected_miles - total_allowed_miles)
    mileage_penalty = excess_miles * excess_mileage_fee

    total_lease_payments_term = lease_monthly_with_tax * lease_term_months
    net_cost_lease_full_term = (
        drive_off + total_lease_payments_term + mileage_penalty + disposition_fee
    )

    # ---------- COST OVER TIME (FOR PLOTS) ----------

    months = list(range(1, horizon_months + 1))
    buy_net_cost_by_month: List[float] = []
    lease_net_cost_by_month: List[float] = []

    for m in months:
        # Buying: net cost = down + payments made + remaining balance − estimated car value
        payments_made = buy_monthly_payment * min(m, loan_term_months)
        remaining_bal = remaining_loan_balance(
            loan_amount, loan_apr, loan_term_months, m
        )
        value_m = linear_depreciation_value(
            purchase_price, end_value_at_horizon, horizon_months, m
        )
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
        st.write(
            f"Total purchase cost (price + fees + tax): "
            f"**${total_purchase_cost:,.0f}**"
        )
        st.write(f"Loan amount financed: **${loan_amount:,.0f}**")
        st.write(
            f"Estimated car value at end of {horizon_years} years: "
            f"**${end_value_at_horizon:,.0f}**"
        )
        st.write(
            f"**Net cost over {horizon_years} years** "
            f"(cash out − equity): `~${net_cost_buy:,.0f}`"
        )

    with col_res_lease:
        st.subheader("Leasing Summary")
        st.metric(
            "Monthly payment"
            f"{' (with tax)' if is_advanced else ''}",
            f"${lease_monthly_with_tax:,.0f}",
        )
        st.write(f"Drive-off (due at signing): **${drive_off:,.0f}**")
        st.write(
            f"Lease payments over {lease_term_months} months"
            f"{' (with tax)' if is_advanced else ''}: "
            f"**${total_lease_payments_term:,.0f}**"
        )
        if mileage_penalty > 0:
            st.write(
                f"Estimated mileage penalties at lease end: "
                f"**${mileage_penalty:,.0f}**"
            )
        st.write(
            f"Disposition / turn-in fee at lease end: "
            f"**${disposition_fee:,.0f}**"
        )
        st.write(
            f"**Total net cost for one full lease**: "
            f"`~${net_cost_lease_full_term:,.0f}`"
        )
        st.write(
            f"**Net cost at {horizon_years} years** "
            f"(same lease assumptions): "
            f"`~${net_cost_lease_at_horizon:,.0f}`"
        )

    st.markdown("---")

    # ---------- CONFIDENCE & RECOMMENDATION ----------

    confidence_text = get_confidence_label(mode, using_estimates)
    st.info(f"**Result confidence:** {confidence_text}")

    diff = net_cost_buy - net_cost_lease_at_horizon

    if diff > 0:
        st.success(
            f"✅ **Leasing is cheaper by approximately "
            f"${abs(diff):,.0f} over {horizon_years} years** under these assumptions."
        )
    elif diff < 0:
        st.success(
            f"✅ **Buying is cheaper by approximately "
            f"${abs(diff):,.0f} over {horizon_years} years** under these assumptions."
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

    # ---------- Detailed Breakdowns ----------

    st.markdown("## 🧾 Detailed Breakdowns")

    tab_amort, tab_lease_cf = st.tabs(
        ["Loan amortization (buy)", "Lease cashflow (lease)"]
    )

    with tab_amort:
        st.markdown("**Loan amortization schedule**")
        if loan_amount > 0 and loan_term_months > 0 and buy_monthly_payment > 0:
            df_amort = build_amortization_schedule(
                loan_amount, loan_apr, loan_term_months, buy_monthly_payment
            )
            st.dataframe(df_amort, use_container_width=True)
            st.markdown("**Remaining balance over time**")
            st.line_chart(
                df_amort.set_index("Month")[["Remaining balance"]]
            )
        else:
            st.info("Enter a positive loan amount, APR, and term to see the schedule.")

    with tab_lease_cf:
        st.markdown("**Lease cashflow breakdown**")
        if lease_term_months > 0 and lease_monthly_with_tax > 0:
            df_cf = build_lease_cashflows(
                lease_term_months,
                drive_off,
                lease_monthly_with_tax,
                mileage_penalty,
                disposition_fee,
            )
            st.dataframe(df_cf, use_container_width=True)
        else:
            st.info("Enter lease details to see the cashflow breakdown.")

    st.caption(
        "The amortization table shows how your loan balance shrinks over time, "
        "while the lease cashflow table shows where every dollar goes in a lease."
    )


if __name__ == "__main__":
    main()
