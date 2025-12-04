import math
import streamlit as st

# ---------- Calculation Helpers ----------

def monthly_loan_payment(loan_amount: float, apr_percent: float, term_months: int) -> float:
    """Standard amortized loan payment."""
    if term_months <= 0:
        return 0.0
    r = apr_percent / 100 / 12  # monthly rate
    if r == 0:
        return loan_amount / term_months
    return loan_amount * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)


def lease_payment_from_mf(cap_cost: float, residual_value: float, money_factor: float, term_months: int) -> float:
    """Typical lease formula: depreciation fee + finance fee."""
    if term_months <= 0:
        return 0.0
    depreciation_fee = (cap_cost - residual_value) / term_months
    finance_fee = (cap_cost + residual_value) * money_factor
    return depreciation_fee + finance_fee


def apr_to_money_factor(apr_percent: float) -> float:
    """Approx convert APR to money factor (roughly APR / 2400)."""
    return apr_percent / 2400


# ---------- Streamlit App ----------

def main():
    st.set_page_config(page_title="Lease vs Buy Calculator", layout="wide")
    st.title("🚗 Lease vs Buy Decision Helper")

    st.markdown(
        "Use this tool to compare **leasing vs buying** a car over a chosen time horizon. "
        "This is an educational tool, not financial advice."
    )

    # Comparison horizon
    st.sidebar.header("Comparison Settings")
    horizon_years = st.sidebar.slider("Comparison horizon (years)", 1, 7, 3)
    horizon_months = horizon_years * 12

    st.sidebar.markdown("---")
    st.sidebar.caption("Adjust buy/lease details in the main panel.")

    col_buy, col_lease = st.columns(2)

    # ---------- BUY INPUTS ----------
    with col_buy:
        st.subheader("🔹 Buying Scenario")

        purchase_price = st.number_input(
            "Negotiated vehicle price ($)",
            min_value=0.0,
            value=35000.0,
            step=500.0,
            format="%.2f",
        )

        tax_rate = st.number_input(
            "Sales tax rate (%)",
            min_value=0.0,
            value=6.25,
            step=0.25,
            format="%.2f",
        )

        buy_fees = st.number_input(
            "Upfront fees (doc, title, etc.) ($)",
            min_value=0.0,
            value=500.0,
            step=50.0,
            format="%.2f",
        )

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

        expected_value_pct = st.slider(
            f"Expected car value at end of {horizon_years} years (% of purchase price)",
            min_value=10,
            max_value=80,
            value=55,
            step=1,
        )

    # ---------- LEASE INPUTS ----------
    with col_lease:
        st.subheader("🔹 Lease Scenario")

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

        lease_term_months = st.number_input(
            "Lease term (months)",
            min_value=12,
            max_value=60,
            value=36,
            step=6,
        )

        residual_pct = st.slider(
            "Residual value at end of lease (% of MSRP)",
            min_value=30,
            max_value=75,
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

        drive_off = st.number_input(
            "Drive-off amount (cash due at signing) ($)",
            min_value=0.0,
            value=2000.0,
            step=250.0,
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

    # ---------- Perform Calculations ----------
    st.markdown("---")
    st.header("📊 Results & Comparison")

    # --- Buy calculations ---
    total_purchase_before_tax = purchase_price + buy_fees
    total_tax = total_purchase_before_tax * (tax_rate / 100)
    total_purchase_cost = total_purchase_before_tax + total_tax

    loan_amount = max(total_purchase_cost - down_payment_buy, 0)
    buy_monthly_payment = monthly_loan_payment(loan_amount, loan_apr, loan_term_months)

    # How many months of payments within horizon?
    months_of_payments = min(horizon_months, loan_term_months)
    total_loan_payments_in_horizon = buy_monthly_payment * months_of_payments

    # Estimate value of car at end of horizon
    estimated_value_end = purchase_price * (expected_value_pct / 100)

    # Net cash outlay for buy (assuming you could sell the car at end of horizon)
    total_out_of_pocket_buy = down_payment_buy + total_loan_payments_in_horizon
    net_cost_buy = total_out_of_pocket_buy - estimated_value_end

    # --- Lease calculations ---
    residual_value = msrp * (residual_pct / 100)
    lease_monthly_payment = lease_payment_from_mf(cap_cost, residual_value, money_factor, lease_term_months)

    # For now, assume comparison horizon is the lease term (or truncate if shorter)
    months_in_lease = min(horizon_months, lease_term_months)
    total_lease_payments_in_horizon = lease_monthly_payment * months_in_lease

    # Mileage penalties (only if horizon = full lease term and you drive more than allowance)
    total_allowed_miles = (allowed_miles_per_year * lease_term_months) / 12
    total_expected_miles = (expected_miles_per_year * lease_term_months) / 12
    excess_miles = max(0, total_expected_miles - total_allowed_miles)
    mileage_penalty = excess_miles * excess_mileage_fee

    total_out_of_pocket_lease = drive_off + total_lease_payments_in_horizon + mileage_penalty
    net_cost_lease = total_out_of_pocket_lease  # no asset at end

    # ---------- Display Results ----------
    col_res_buy, col_res_lease = st.columns(2)

    with col_res_buy:
        st.subheader("Buying Summary")
        st.metric("Monthly payment", f"${buy_monthly_payment:,.0f}")
        st.write(f"**Total paid in {horizon_years} years** (down + loan payments): "
                 f"${total_out_of_pocket_buy:,.0f}")
        st.write(f"Estimated car value at end of {horizon_years} years: "
                 f"${estimated_value_end:,.0f}")
        st.write(f"**Net cost over {horizon_years} years**: "
                 f"`${net_cost_buy:,.0f}`")

    with col_res_lease:
        st.subheader("Leasing Summary")
        st.metric("Monthly payment", f"${lease_monthly_payment:,.0f}")
        st.write(f"Drive-off (due at signing): ${drive_off:,.0f}")
        st.write(f"Lease payments over {months_in_lease} months: "
                 f"${total_lease_payments_in_horizon:,.0f}")
        if mileage_penalty > 0:
            st.write(f"Estimated mileage penalties: ${mileage_penalty:,.0f}")
        st.write(f"**Net cost over {horizon_years} years**: "
                 f"`${net_cost_lease:,.0f}`")

    st.markdown("---")

    # ---------- Recommendation ----------
    diff = net_cost_buy - net_cost_lease

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
        "These results are estimates only. Real-world offers, taxes, maintenance, and fees may vary."
    )


if __name__ == '__main__':
    main()
