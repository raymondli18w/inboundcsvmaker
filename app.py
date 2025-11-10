import streamlit as st
import pandas as pd
from io import StringIO

# =========================
# Column synonyms mapping
# =========================
COLUMN_SYNONYMS = {
    'Sales Order No.': ['sales order no', 'sales order number', 'hdr', 'hdr ref', 'po ref', 'order', 'header reference', 'header ref', 'po number', 'ref', 'reference', 'so no', 'po', 'order no'],
    'Pick Date': ['pick date', 'date picked', 'ship date', 'date ship', 'order date', 'date', 'receipt date', 'date to ship', 'date shipped', 'pickdate'],
    'Item No.': ['item no', 'item number', 'product', 'sku', 'item', 'product code'],
    'Each Qty': ['each qty', 'quantity', 'qty', 'units'],
    'WHSE': ['whse', 'warehouse', 'warehouse code'],
    'Ship To': ['ship to', 'recipient', 'consign', 'name', 'to', 'customer name'],
    'Ship To Code': ['ship to code', 'ship code', 'consign code', 'shipto code'],
    'Ship To Address 2': ['ship addr 2', 'ship address 2', 'address 2', 'adr 2'],
    'Street': ['street', 'address', 'addr 1', 'ship from address', 'ship to address', 'consign address', 'address line 1'],
    'City': ['city', 'town', 'county', 'municipality'],
    'Zip Code': ['zip code', 'zip', 'postal', 'postal code', 'postcode'],
    'Country/Region': ['country/region', 'country', 'nation'],
    'state': ['state', 'province', 'region'],
    'Ref 1': ['ref 1', 'reference 1', 'header ref 1', 'header reference 1'],
    'Ref 2': ['ref 2', 'reference 2', 'header ref 2', 'header reference 2'],
    'Ref 3': ['ref 3', 'reference 3', 'header ref 3', 'header reference 3'],
    'Pro Number': ['pro number', 'pro', 'tracking no', 'tracking'],
    'Carrier Code': ['carrier code', 'scac', 'scac code'],
    'Carrier Name': ['carrier', 'carrier name', 'scac name', 'truck', 'truck name'],
    'CLIENT': ['client', 'customer id', 'depositor', 'agent', 'client code']
}

# =========================
# Address Validation
# =========================
CANADA_PROVINCES = ["AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"]
US_STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
             "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
             "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"]

def validate_address(row):
    country = str(row.get("Country/Region", "")).upper()
    province = str(row.get("state", "")).upper()
    postal = str(row.get("Zip Code", "")).replace(" ", "")
    
    if country not in ["CA", "US"]:
        return "Invalid country"
    if country == "CA" and len(postal) > 7:
        return "Invalid Canadian postal code"
    if country == "US" and len(postal) > 6:
        return "Invalid US ZIP code"
    if country == "CA" and province not in CANADA_PROVINCES:
        return "Invalid province"
    if country == "US" and province not in US_STATES:
        return "Invalid state"
    return "Valid"

# =========================
# Trim helper
# =========================
def trim_text(val, max_len):
    if pd.isna(val):
        return ''
    return str(val)[:max_len]

# =========================
# Standardize headers
# =========================
def standardize_headers(df):
    mapping = {}
    for std_col, synonyms in COLUMN_SYNONYMS.items():
        for col in df.columns:
            if str(col).strip().lower() in [s.lower() for s in synonyms]:
                mapping[col] = std_col
    df.rename(columns=mapping, inplace=True)
    return df

# =========================
# Fill blank/mixed rows with first valid row
# =========================
def fill_blank_rows(df):
    first_valid_row = None
    for idx, row in df.iterrows():
        if first_valid_row is None and row.notna().all():
            first_valid_row = row.copy()
        elif first_valid_row is not None:
            for col in df.columns:
                if pd.isna(row[col]) or row[col] == '':
                    row[col] = first_valid_row[col]
            if 'CLIENT' in df.columns:
                row['CLIENT'] = 'deleteme'
    return df

# =========================
# Address consistency check
# =========================
def check_address_consistency(df):
    mismatch_flag = []
    addr_cols = ['Ship To', 'Ship To Address 2', 'Street', 'City', 'state', 'Zip Code', 'Country/Region']
    for _, row in df.iterrows():
        so_no = str(row.get('Sales Order No.', ''))
        if so_no == '':
            mismatch_flag.append(False)
            continue
        same_so_rows = df[df['Sales Order No.'] == so_no]
        current_addr = tuple(row.get(col, '') for col in addr_cols)
        mismatch = any(
            tuple(r.get(col, '') for col in addr_cols) != current_addr
            for _, r in same_so_rows.iterrows()
        )
        mismatch_flag.append(mismatch)
    df['Address_Mismatch'] = mismatch_flag
    return df

# =========================
# Main TSV Processing
# =========================
def process_inbound_tsv(raw_text):
    try:
        df = pd.read_csv(StringIO(raw_text), delimiter='\t', dtype=str)
    except Exception as e:
        st.error(f"Error parsing TSV data: {e}")
        return None

    df = standardize_headers(df)

    optional_cols = [
        'Ship To', 'Ship To Code', 'Ship To Address 2', 'Street', 'City', 'state', 'Zip Code', 'Country/Region',
        'Customer PO', 'Ref 1', 'Ref 2', 'Ref 3', 'Carrier Code', 'Carrier Name', 'WHSE'
    ]
    for col in optional_cols:
        if col not in df.columns:
            df[col] = ''

    df = fill_blank_rows(df)
    df['Validation Status'] = df.apply(validate_address, axis=1)

    df = check_address_consistency(df)
    if df['Address_Mismatch'].any():
        st.error("⚠️ Address mismatch detected! Some Sales Order Numbers have conflicting addresses.")
        st.dataframe(df[df['Address_Mismatch']][['Sales Order No.', 'Ship To', 'Street', 'City', 'state', 'Zip Code', 'Country/Region']])
        return None

    output_rows = []
    all_cols = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + [f"A{chr(i)}" for i in range(ord('A'), ord('Z') + 1)]

    for _, row in df.iterrows():
        has_order = pd.notna(row.get('Sales Order No.', ''))
        has_item = pd.notna(row.get('Item No.', ''))
        if has_order and has_item and row['Validation Status'] == "Valid":
            out_row = {col: '' for col in all_cols}
            out_row['A'] = 'BC'
            out_row['B'] = trim_text(row['CLIENT'], 10)
            out_row['C'] = trim_text(row['Sales Order No.'], 30)
            out_row['D'] = trim_text(row.get('Customer PO', ''), 30)
            out_row['E'] = row['Pick Date']  # Note: may be empty or invalid — consider formatting if needed
            out_row['G'] = trim_text(row['Ship To Code'], 10)
            out_row['H'] = trim_text(row['Ship To'], 45)
            out_row['J'] = trim_text(row['Street'], 30)
            out_row['K'] = trim_text(row['Ship To Address 2'], 30)
            out_row['L'] = trim_text(row['City'], 10)
            out_row['M'] = trim_text(row['state'], 10)
            out_row['N'] = trim_text(row['Zip Code'], 10)
            out_row['O'] = trim_text(row['Country/Region'], 10)
            out_row['P'] = trim_text(row['Carrier Code'], 10)
            out_row['Q'] = trim_text(row['Carrier Name'], 20)
            out_row['R'] = trim_text(row['WHSE'], 10)
            out_row['S'] = trim_text(row['Ref 1'], 30)
            out_row['T'] = trim_text(row['Ref 2'], 30)
            out_row['U'] = trim_text(row['Ref 3'], 30)
            out_row['V'] = trim_text(row['Item No.'], 20)
            output_rows.append(out_row)

    if not output_rows:
        st.warning("No valid rows found to process.")
        return None

    return pd.DataFrame(output_rows)

# =========================
# Streamlit UI
# =========================
st.title("Inbound TSV to CSV Converter")
st.markdown("Paste your TSV data below. Sales Order No. and Item No. must be present. Addresses are validated for CA/US. Conflicting addresses are flagged.")

raw_data = st.text_area("Paste your TSV data here:")

if st.button("Generate Inbound CSV"):
    if not raw_data.strip():
        st.warning("Please paste your TSV data.")
    else:
        processed_df = process_inbound_tsv(raw_data)
        if processed_df is not None:
            csv_data = processed_df.to_csv(index=False, header=False, encoding='cp1252').replace('\n', '\r\n')
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="inbound_output.csv",
                mime="text/csv"
            )
            st.success("CSV generated! You can now download it.")