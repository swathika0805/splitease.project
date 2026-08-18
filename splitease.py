import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import heapq

# ==================================================
# PAGE SETTINGS
# ==================================================
st.set_page_config(page_title="SplitEase", page_icon="💸", layout="wide")

st.title("💸 SplitEase")
st.subheader("Graph-Based Group Expense Splitter")
st.write(
    "Models group expenses as a **weighted directed graph** (who owes whom), "
    "then runs a **debt-simplification algorithm** to settle everyone using the "
    "**minimum number of transactions** — like Splitwise."
)

# ==================================================
# 1. GRAPH CLASS (adjacency dict of debts, built from scratch)
#    edge u -> v with weight w means "u owes v amount w"
# ==================================================
class DebtGraph:
    def __init__(self):
        self.adj = {}   # {person: {other_person: amount_owed}}

    def add_person(self, name):
        self.adj.setdefault(name, {})

    def add_debt(self, debtor, creditor, amount):
        """debtor owes creditor `amount`. Merges with any existing/opposite debt."""
        if debtor == creditor or amount <= 0:
            return
        self.add_person(debtor)
        self.add_person(creditor)

        # If creditor already owes debtor, net it out first
        existing_reverse = self.adj[creditor].get(debtor, 0)
        if existing_reverse > 0:
            if existing_reverse > amount:
                self.adj[creditor][debtor] = existing_reverse - amount
                return
            elif existing_reverse < amount:
                del self.adj[creditor][debtor]
                amount -= existing_reverse
            else:
                del self.adj[creditor][debtor]
                return

        self.adj[debtor][creditor] = self.adj[debtor].get(creditor, 0) + amount

    def net_balances(self):
        """Positive balance = should RECEIVE money. Negative = OWES money."""
        balance = {p: 0.0 for p in self.adj}
        for debtor, creditors in self.adj.items():
            for creditor, amount in creditors.items():
                balance[debtor] -= amount
                balance[creditor] += amount
        return balance

    def all_edges(self):
        edges = []
        for u, creditors in self.adj.items():
            for v, amt in creditors.items():
                if amt > 0:
                    edges.append((u, v, round(amt, 2)))
        return edges


# ==================================================
# 2. MIN-TRANSACTION SETTLEMENT ALGORITHM
#    Greedy: always match the biggest creditor with the biggest debtor
#    using two heaps (max-heap via negated values)
# ==================================================
def simplify_debts(balances):
    """
    balances: dict {person: net_balance}
    Returns list of (payer, receiver, amount) — minimum transactions to settle all debts.
    """
    creditors = []  # max-heap of (-amount, person) who should RECEIVE
    debtors = []    # max-heap of (-amount, person) who OWES

    for person, amt in balances.items():
        amt = round(amt, 2)
        if amt > 0.001:
            heapq.heappush(creditors, (-amt, person))
        elif amt < -0.001:
            heapq.heappush(debtors, (amt, person))  # amt is negative already

    transactions = []

    while creditors and debtors:
        credit_amt, creditor = heapq.heappop(creditors)
        debt_amt, debtor = heapq.heappop(debtors)
        credit_amt = -credit_amt          # amount creditor should receive
        debt_amt = -debt_amt              # amount debtor owes

        settle_amount = min(credit_amt, debt_amt)
        transactions.append((debtor, creditor, round(settle_amount, 2)))

        remaining_credit = round(credit_amt - settle_amount, 2)
        remaining_debt = round(debt_amt - settle_amount, 2)

        if remaining_credit > 0.001:
            heapq.heappush(creditors, (-remaining_credit, creditor))
        if remaining_debt > 0.001:
            heapq.heappush(debtors, (-remaining_debt, debtor))

    return transactions


# ==================================================
# 3. SESSION STATE
# ==================================================
if "people" not in st.session_state:
    st.session_state.people = []
if "graph" not in st.session_state:
    st.session_state.graph = DebtGraph()
if "expenses" not in st.session_state:
    st.session_state.expenses = []

graph = st.session_state.graph

# ==================================================
# 4. ADD PEOPLE
# ==================================================
st.header("1️⃣ Add People to the Group")
new_person = st.text_input("Enter a person's name", placeholder="e.g. Arjun")
if st.button("➕ Add Person"):
    name = new_person.strip().title()
    if not name:
        st.warning("⚠️ Enter a valid name.")
    elif name in st.session_state.people:
        st.warning("⚠️ This person is already added.")
    else:
        st.session_state.people.append(name)
        graph.add_person(name)
        st.success(f"Added {name}")

if st.session_state.people:
    st.write("**Group members:**", ", ".join(st.session_state.people))
else:
    st.info("Add at least 2 people to record an expense.")

# ==================================================
# 5. ADD EXPENSE (split equally among selected people)
# ==================================================
st.header("2️⃣ Add an Expense")

if len(st.session_state.people) >= 2:
    col1, col2 = st.columns(2)
    with col1:
        paid_by = st.selectbox("Who paid?", st.session_state.people)
        amount = st.number_input("Total amount (₹)", min_value=0.0, step=10.0)
    with col2:
        split_among = st.multiselect(
            "Split among (include payer if they share too)",
            st.session_state.people,
            default=st.session_state.people
        )
    description = st.text_input("What was it for?", placeholder="e.g. Dinner, Cab, Hotel")

    if st.button("💰 Add Expense"):
        if amount <= 0:
            st.warning("⚠️ Enter a valid amount.")
        elif len(split_among) < 2:
            st.warning("⚠️ Select at least 2 people to split among.")
        else:
            share = amount / len(split_among)
            for person in split_among:
                if person != paid_by:
                    graph.add_debt(debtor=person, creditor=paid_by, amount=share)
            st.session_state.expenses.append({
                "desc": description or "Expense",
                "paid_by": paid_by,
                "amount": amount,
                "split_among": split_among,
                "share": round(share, 2)
            })
            st.success(f"Added: {description or 'Expense'} — ₹{amount} paid by {paid_by}, split {len(split_among)} ways (₹{share:.2f} each)")
else:
    st.info("Add at least 2 people first.")

# ==================================================
# 6. EXPENSE HISTORY
# ==================================================
if st.session_state.expenses:
    st.header("3️⃣ Expense History")
    for i, e in enumerate(st.session_state.expenses, 1):
        st.write(f"{i}. **{e['desc']}** — ₹{e['amount']} paid by {e['paid_by']}, "
                  f"split among {', '.join(e['split_among'])} (₹{e['share']} each)")

# ==================================================
# 7. ANALYZE — GRAPH VIEW + SETTLEMENT
# ==================================================
if st.button("🔍 Calculate Settlements"):

    edges = graph.all_edges()

    if not edges:
        st.info("No debts recorded yet — add some expenses first.")
    else:
        # ----------------------------------------
        # Raw debt graph (before simplification)
        # ----------------------------------------
        st.header("📊 Raw Debt Graph (Before Simplification)")
        st.write(f"Total individual debts: **{len(edges)}**")
        for u, v, amt in edges:
            st.write(f"🔴 {u} owes {v}: ₹{amt}")

        G_before = nx.DiGraph()
        for u, v, amt in edges:
            G_before.add_edge(u, v, weight=amt)

        fig1, ax1 = plt.subplots(figsize=(8, 5))
        pos1 = nx.spring_layout(G_before, seed=42)
        nx.draw(G_before, pos1, ax=ax1, with_labels=True, node_color="#FF9800",
                node_size=1800, font_size=9, arrows=True, edge_color="#999999")
        edge_labels1 = {(u, v): f"₹{d['weight']}" for u, v, d in G_before.edges(data=True)}
        nx.draw_networkx_edge_labels(G_before, pos1, edge_labels=edge_labels1, ax=ax1, font_size=8)
        st.pyplot(fig1)

        # ----------------------------------------
        # Net balances
        # ----------------------------------------
        st.header("📋 Net Balance Per Person")
        balances = graph.net_balances()
        for person, bal in balances.items():
            if bal > 0.001:
                st.write(f"🟢 {person} should **receive** ₹{bal:.2f}")
            elif bal < -0.001:
                st.write(f"🔴 {person} should **pay** ₹{-bal:.2f}")
            else:
                st.write(f"⚪ {person} is settled up")

        # ----------------------------------------
        # Simplified settlement (min transactions)
        # ----------------------------------------
        st.header("✅ Simplified Settlement (Minimum Transactions)")
        transactions = simplify_debts(balances)

        if not transactions:
            st.success("🎉 Everyone is already settled!")
        else:
            st.write(f"Reduced to **{len(transactions)}** transaction(s) "
                      f"(from {len(edges)} raw debts):")
            for payer, receiver, amt in transactions:
                st.write(f"💸 **{payer}** pays **{receiver}**: ₹{amt}")

            G_after = nx.DiGraph()
            for payer, receiver, amt in transactions:
                G_after.add_edge(payer, receiver, weight=amt)

            fig2, ax2 = plt.subplots(figsize=(8, 5))
            pos2 = nx.spring_layout(G_after, seed=42)
            nx.draw(G_after, pos2, ax=ax2, with_labels=True, node_color="#4CAF50",
                    node_size=1800, font_size=9, arrows=True, edge_color="#999999")
            edge_labels2 = {(u, v): f"₹{d['weight']}" for u, v, d in G_after.edges(data=True)}
            nx.draw_networkx_edge_labels(G_after, pos2, edge_labels=edge_labels2, ax=ax2, font_size=8)
            st.pyplot(fig2)

# ==================================================
# 8. RESET
# ==================================================
st.divider()
if st.button("🔄 Reset Everything"):
    st.session_state.people = []
    st.session_state.graph = DebtGraph()
    st.session_state.expenses = []
    st.rerun()