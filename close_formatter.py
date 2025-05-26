import streamlit as st
import pandas as pd
import io
import re

st.title("Euclid's Close CRM Formatter")

# US State abbreviation to full name mapping
state_map = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
}

def is_valid(val):
    return pd.notnull(val) and str(val).strip() and str(val).strip().lower() not in ['nan', 'none', '']

def get_source_cols(df):
    return [col for col in df.columns if col.lower().startswith("source:")]

def make_cols_unique(cols):
    counts = {}
    out = []
    for col in cols:
        if col not in counts:
            counts[col] = 0
            out.append(col)
        else:
            counts[col] += 1
            out.append(f"{col}.{counts[col]}")
    return out

def dedup_same_content_columns(df, prefix="Source:"):
    base_names = {}
    for col in df.columns:
        if col.startswith(prefix):
            root = col
            if "." in col:
                root = col.split(".")[0]
            base_names.setdefault(root, []).append(col)
    cols_to_drop = []
    for root, col_list in base_names.items():
        if len(col_list) > 1:
            sub_df = df[col_list]
            if (sub_df.nunique(axis=1) <= 1).all():
                cols_to_drop.extend(col_list[1:])
    df = df.drop(columns=cols_to_drop)
    return df

def deabbr_state(val):
    if pd.isna(val):
        return val
    v = str(val).strip().upper()
    return state_map.get(v, val)

def detect_dynamic_numbers(df, regex):
    numbers = set()
    for col in df.columns:
        m = re.match(regex, col)
        if m:
            numbers.add(int(m.group(1)))
    return sorted(numbers)

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = make_cols_unique(df.columns)  # Ensure unique column names!
    df = dedup_same_content_columns(df)         # Drop duplicate "Source:" columns with identical content

    source_cols = get_source_cols(df)

    # --- De-abbreviate state fields in "Source:" columns ---
    state_cols = [col for col in source_cols if "state" in col.lower()]
    for col in state_cols:
        df[col] = df[col].apply(deabbr_state)

    # --- Dynamically detect address, personal, relative numbers ---
    address_nums = detect_dynamic_numbers(df, r'Address(\d+): Address Full Address')
    address_phone_nums = detect_dynamic_numbers(df, r'Address1: Associated Phone (\d+)')
    # For all addresses, get their individual phone number counts
    address_phone_dict = {}
    for addr_num in address_nums:
        phones = detect_dynamic_numbers(df, fr'Address{addr_num}: Associated Phone (\d+)')
        address_phone_dict[addr_num] = phones

    personal_nums = detect_dynamic_numbers(df, r'Phone(\d+): Phone Number')
    relative_nums = detect_dynamic_numbers(df, r'Relative(\d+): Phone 1 Number')
    relative_phone_nums = detect_dynamic_numbers(df, r'Relative1: Phone (\d+) Number')
    # For all relatives, get their individual phone number counts
    relative_phone_dict = {}
    for rel_num in relative_nums:
        phones = detect_dynamic_numbers(df, fr'Relative{rel_num}: Phone (\d+) Number')
        relative_phone_dict[rel_num] = phones

    sanity_summary = {
        "Original records": len(df),
        "Property Phones": 0,
        "Personal Phones": 0,
        "Relative Phones": 0,
        "Total Output Records": 0
    }

    records = []

    for idx, row in df.iterrows():
        # --- Address/Property Phones ---
        for addr_num in address_nums:
            addr_col = f'Address{addr_num}: Address Full Address'
            for phone_num in address_phone_dict[addr_num]:
                phone_col = f'Address{addr_num}: Associated Phone {phone_num}'
                if addr_col in df.columns and phone_col in df.columns:
                    phone_val = row[phone_col]
                    addr_val = row[addr_col]
                    if is_valid(phone_val):
                        rec = {k: row[k] for k in source_cols}
                        rec["Phone number type"] = f"Address {addr_num} : Phone {phone_num}"
                        rec["Phone number"] = phone_val
                        records.append(rec)
                        sanity_summary["Property Phones"] += 1

        # --- Personal (Skip Trace) Phones ---
        for phone_idx in personal_nums:
            phone_col = f'Phone{phone_idx}: Phone Number'
            if phone_col in df.columns:
                phone_val = row[phone_col]
                if is_valid(phone_val):
                    rec = {k: row[k] for k in source_cols}
                    rec["Phone number type"] = f"Personal : Phone {phone_idx}"
                    rec["Phone number"] = phone_val
                    records.append(rec)
                    sanity_summary["Personal Phones"] += 1

        # --- Relative Phones ---
        for rel_idx in relative_nums:
            for phone_num in relative_phone_dict[rel_idx]:
                phone_col = f'Relative{rel_idx}: Phone {phone_num} Number'
                if phone_col in df.columns:
                    phone_val = row[phone_col]
                    if is_valid(phone_val):
                        rec = {k: row[k] for k in source_cols}
                        rec["Phone number type"] = f"Relative {rel_idx} : Phone {phone_num}"
                        rec["Phone number"] = phone_val
                        records.append(rec)
                        sanity_summary["Relative Phones"] += 1

    # Create output DataFrame
    out_df = pd.DataFrame(records)
    sanity_summary["Total Output Records"] = len(out_df)

    # --- Sanity Check Section ---
    st.header("Sanity Check Section")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Original Data Quick Look")
        st.write(df.head(5))   # Show all original columns

    with col2:
        st.subheader("Transformed Data Quick Look")
        st.write(out_df.head(10))

    st.markdown("### Data Quality Summary")
    st.json(sanity_summary, expanded=False)

    # More detailed checks
    st.markdown("#### Detailed Checks")
    # Check for missing phone numbers in output
    missing_phones = out_df["Phone number"].isnull().sum() if not out_df.empty else 0
    duplicate_phones = out_df["Phone number"].duplicated().sum() if not out_df.empty else 0
    st.write(f"Missing phone numbers in output: {missing_phones}")
    st.write(f"Duplicate phone numbers in output: {duplicate_phones}")

    if not out_df.empty:
        st.success(f"Transformed {len(out_df)} phone records from {len(df)} input rows.")
        st.dataframe(out_df, use_container_width=True)
        # Download
        csv_buffer = io.StringIO()
        out_df.to_csv(csv_buffer, index=False)
        st.download_button(
            "Download as CSV",
            data=csv_buffer.getvalue(),
            file_name="transformed_phone_records.csv",
            mime="text/csv"
        )
    else:
        st.warning("No valid phone records found.")

st.markdown("""
---
**Instructions:**  
- Upload a CSV file.
- All 'Source:' columns are preserved per record (deduplicated if identical).
- State abbreviations in 'Source:' columns are expanded to full names.
- Each phone number becomes a new row, with type and value, plus source fields.
- See sanity checks for data quality before exporting.
""")
