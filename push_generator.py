import pandas as pd
import glob
import os

# --- 1. Барлық деректерді жүктеу және біріктіру ---
try:
    # 1.1. Клиенттер туралы негізгі файлды оқу (clients.xlsx, clients.xls немесе clients.csv)
    client_file_found = False
    if os.path.exists('clients.xlsx'):
        df_clients = pd.read_excel('clients.xlsx')
        client_file_found = True
    elif os.path.exists('clients.xls'): # *.xls кеңейтімін тексеру
        df_clients = pd.read_excel('clients.xls')
        client_file_found = True
    elif os.path.exists('clients.csv'):
        df_clients = pd.read_csv('clients.csv')
        client_file_found = True
    
    if not client_file_found:
        raise FileNotFoundError("Клиенттер файлы ('clients.xlsx', 'clients.xls' немесе 'clients.csv') табылмады.")

    # 1.2. Бумадағы барлық транзакция файлдарын табу және біріктіру
    # Енді .xlsx, .xls және .csv кеңейтімдерін іздейміз
    transaction_files_xls = glob.glob('client_*_transactions_3m.xls')
    transaction_files_xlsx = glob.glob('client_*_transactions_3m.xlsx')
    transaction_files_csv = glob.glob('client_*_transactions_3m.csv')
    transaction_files = transaction_files_xls + transaction_files_xlsx + transaction_files_csv
    
    if not transaction_files:
        raise FileNotFoundError("Транзакциялар файлдары ('client_XX_transactions_3m.xls/xlsx/csv') табылмады. Файл атауларын тексеріңіз.")
        
    transactions_list = []
    for file in transaction_files:
        if file.endswith('.csv'):
            df_temp = pd.read_csv(file)
        else: # .xls немесе .xlsx
            df_temp = pd.read_excel(file)
        transactions_list.append(df_temp)
    df_transactions = pd.concat(transactions_list, ignore_index=True)
    print(f"{len(transaction_files)} транзакция файлы сәтті біріктірілді.")

    # 1.3. Бумадағы барлық аударымдар файлдарын табу және біріктіру
    # Енді .xlsx, .xls және .csv кеңейтімдерін іздейміз
    transfer_files_xls = glob.glob('client_*_transfers_3m.xls')
    transfer_files_xlsx = glob.glob('client_*_transfers_3m.xlsx')
    transfer_files_csv = glob.glob('client_*_transfers_3m.csv')
    transfer_files = transfer_files_xls + transfer_files_xlsx + transfer_files_csv

    if not transfer_files:
        raise FileNotFoundError("Аударымдар файлдары ('client_XX_transfers_3m.xls/xlsx/csv') табылмады. Файл атауларын тексеріңіз.")

    transfers_list = []
    for file in transfer_files:
        if file.endswith('.csv'):
            df_temp = pd.read_csv(file)
        else: # .xls немесе .xlsx
            df_temp = pd.read_excel(file)
        transfers_list.append(df_temp)
    df_transfers = pd.concat(transfers_list, ignore_index=True)
    print(f"{len(transfer_files)} аударымдар файлы сәтті біріктірілді.")

except FileNotFoundError as e:
    print(f"Қате: {e}")
    print("Файлдардың дұрыс аталғанына және скриптпен бірге бір бумада екеніне көз жеткізіңіз.")
    exit()
except Exception as e:
    print(f"Белгісіз қате пайда болды: {e}")
    print("Excel файлдарын оқу үшін 'pip install openpyxl' командасын орындадыңыз ба?")
    exit()

# --- 2. Әрбір клиент үшін агрегацияланған профиль жасау ---
def create_client_profile(client_id, client_info, transactions, transfers):
    profile = client_info.copy()
    
    cust_trans = transactions[transactions['client_code'] == client_id]
    cust_transfers = transfers[transfers['client_code'] == client_id]
    
    profile['total_spending'] = cust_trans['amount'].sum()
    
    category_spending = cust_trans.groupby('category')['amount'].sum().sort_values(ascending=False)
    profile['top_categories'] = category_spending.head(3).index.tolist()
    
    travel_cats = ['Такси', 'Отели', 'Путешествия']
    online_cats = ['Едим дома', 'Смотрим дома', 'Играем дома']
    premium_cats = ['Ювелирные украшения', 'Косметика и Парфюмерия', 'Кафе и рестораны']

    profile['travel_spending'] = cust_trans[cust_trans['category'].isin(travel_cats)]['amount'].sum()
    profile['online_spending'] = cust_trans[cust_trans['category'].isin(online_cats)]['amount'].sum()
    profile['premium_spending'] = cust_trans[cust_trans['category'].isin(premium_cats)]['amount'].sum()
    
    profile['fx_operations_count'] = cust_transfers[cust_transfers['type'].isin(['fx_buy', 'fx_sell'])].shape[0]
    
    return profile

# --- 3. Өнімді ұсыну логикасы ---
def recommend_product(profile):
    scores = {}
    
    scores['Карта для путешествий'] = profile.get('travel_spending', 0) * 0.04
    
    balance_score = 0
    if profile.get('avg_monthly_balance_KZT', 0) > 6000000:
        balance_score = profile.get('total_spending', 0) * 0.04
    elif profile.get('avg_monthly_balance_KZT', 0) > 1000000:
        balance_score = profile.get('total_spending', 0) * 0.03
    else:
        balance_score = profile.get('total_spending', 0) * 0.02
    scores['Премиальная карта'] = balance_score + profile.get('premium_spending', 0) * 0.04

    diversity_score = len(profile.get('top_categories', [])) * 5000
    scores['Кредитная карта'] = profile.get('online_spending', 0) * 0.1 + diversity_score
    
    scores['Обмен валют'] = profile.get('fx_operations_count', 0) * 15000
    
    avg_balance = profile.get('avg_monthly_balance_KZT', 0)
    if avg_balance > 100000 and profile.get('total_spending', 0) < avg_balance * 2:
        scores['Депозит Накопительный'] = avg_balance * 0.155
    else:
        scores['Депозит Накопительный'] = 0

    if not scores or all(value == 0 for value in scores.values()):
        return 'Депозит Накопительный', scores

    best_product = max(scores, key=scores.get)
    return best_product, scores

# --- 4. Push-хабарламаны құрастыру ---
def generate_push_notification(profile, product):
    name = profile.get('name', 'Клиент')
    
    if product == 'Карта для путешествий':
        travel_spent = int(profile.get('travel_spending', 0))
        cashback_estimate = int(travel_spent * 0.04)
        return f"{name}, өткен 3 айда саяхат пен таксиге {travel_spent:,} ₸ жұмсапсыз. Саяхат картасымен ≈{cashback_estimate:,} ₸ қайтарар едіңіз. Қолданбада рәсімдеу.".replace(',', ' ')

    if product == 'Премиальная карта':
        return f"{name}, сіздің шоттағы жоғары қалдық үлкен мүмкіндіктер береді. Премиум картамен барлық сатылымнан 4%-ға дейін кешбэк алып, қолма-қол ақшаны комиссиясыз шеше аласыз. Қазір қосылу."

    if product == 'Кредитная карта':
        if len(profile.get('top_categories', [])) >= 2:
            cats = ', '.join(profile.get('top_categories', [])[:2])
            return f"{name}, сіздің негізгі шығындарыңыз — {cats}. Кредиттік картамен сүйікті санаттарға 10% дейін кешбэк алыңыз. Картаны ашу."
        else:
            return f"{name}, шығындарыңызды оңтайландырыңыз. Кредиттік картамен сүйікті санаттарға 10% дейін кешбэк алыңыз. Картаны ашу."

    if product == 'Обмен валют':
        return f"{name}, сіз шетел валютасымен операциялар жасайтыныңызды байқадық. Қосымшада валютаны тиімді курспен, комиссиясыз айырбастаңыз. Бағамды баптау."
        
    if product == 'Депозит Накопительный':
        balance = int(profile.get('avg_monthly_balance_KZT', 0))
        return f"{name}, шотыңызда {balance:,} ₸ көлемінде бос қаражат бар. Оны 15,50% жылдық мөлшерлемемен депозитке салып, ақшаңызды өсіріңіз. Депозит ашу.".replace(',', ' ')

    return f"{name}, сізге {product} өнімі қызықты болуы мүмкін. Толығырақ білу."

# --- 5. Негізгі процесс ---
results = []
for index, client_row in df_clients.iterrows():
    client_id = client_row['client_code']
    
    client_profile = create_client_profile(client_id, client_row.to_dict(), df_transactions, df_transfers)
    best_product, scores = recommend_product(client_profile)
    push_message = generate_push_notification(client_profile, best_product)
    
    results.append({
        'client_code': client_id,
        'product': best_product,
        'push_notification': push_message
    })

df_results = pd.DataFrame(results)
df_results.to_csv('final_push_notifications.csv', index=False, encoding='utf-8-sig')

print("\nТапсырма сәтті аяқталды!")
print(f"Барлығы {len(df_results)} клиент үшін нәтиже дайын.")
print("Нәтижелер 'final_push_notifications.csv' файлына сақталды.")