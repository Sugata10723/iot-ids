import pandas as pd
import os
import json
from sklearn.model_selection import train_test_split

########################################
# Dataset_UNSW_NB15_1
# 元がAttackが少ないデータセット
# 元の特徴量は49個
# 最終的な変換後の特徴量数は72
# 1, 3, 47行目に異なるデータ型が混在している
# dsportはobject型であり、16進数と10進数が混在するため、10進数に統一する。異常な値は削除する
# sportはint64型であり、10進数で記録されているため、そのまま使用する。47312, 116466に文字列が混在するので、削除する
# dstip, srcipはobject型であり、IPアドレスで記録されているため、4分割して整数値(int64)に変換する
########################################
class Dataset_UNSW_NB15_1:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self, nrows):
        self.nrows = nrows
        self.CONFIG_FILE_PATH = os.path.join(self.BASE_DIR, 'config', 'config_UNSW_NB15_1.json')
        self.config = self.load_config()
        self.DATA_FILE_PATH = f"{self.BASE_DIR}/data/UNSW_NB15/UNSW-NB15_1.csv"
        self.DATA_FEATURES_FILE_PATH = f"{self.BASE_DIR}/data/UNSW_NB15/test.csv"
        self.data = None
        self.labels = None
        self.X_train = None # Pandas DataFrame
        self.X_test = None # Pandas DataFrame
        self.y_train = None # Pandas Series
        self.y_test = None # Pandas Series

        self.load_data()
        self.split_data()

    def load_config(self):
        with open(self.CONFIG_FILE_PATH, 'r') as f:
            return json.load(f)

    def convert_to_decimal(self, x):
        if not isinstance(x, str):
            return x
        try:
            # 16進数として解釈して変換
            return int(x, 16)
        except ValueError:
            try:
                # 10進数として解釈
                return int(x)
            except ValueError:
                # 無効な値が渡された場合は-1を返す
                return -1

    def split_ip(self, ip):
        return list(map(int, ip.split('.')))

    def split_data(self, test_size=0.3, random_state=42):
        self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
            self.data, self.labels, test_size=test_size, random_state=random_state
        )
        self.y_train = self.y_train.values # Pandas Series -> NumPy Array
        self.y_test = self.y_test.values # Pandas Series -> NumPy Array


    def bitwise(self, data):
        data = data.copy()

        # IPアドレスを32ビットのバイナリ文字列に変換する関数
        def ip_to_bin(ip):
            return ''.join([format(int(x), '08b') for x in ip.split('.')])

        # dstipとsrcipを32ビットのバイナリ文字列に変換
        data['dstip_bin'] = data['dstip'].apply(ip_to_bin)
        data['srcip_bin'] = data['srcip'].apply(ip_to_bin)

        # バイナリ文字列を個々のビットに分割し、新しい特徴量として追加
        for i in range(32):
            data[f'dstip_bit_{i}'] = data['dstip_bin'].apply(lambda x: int(x[i]))
            data[f'srcip_bit_{i}'] = data['srcip_bin'].apply(lambda x: int(x[i]))

        # バイナリ文字列の特徴量はもう不要なので削除
        data.drop(columns=['dstip_bin', 'srcip_bin', 'dstip', 'srcip'], inplace=True)

        # カテゴリ変数にdstipを追加
        for i in range(32):
            self.config['categorical_columns'].append(f'dstip_bit_{i}')
            self.config['categorical_columns'].append(f'srcip_bit_{i}')

        return data

    def preprocess(self, data):
        data = data.copy()
        # 不要なカラムを削除
        data.drop(columns=self.config['unwanted_columns'], inplace=True)

        # dsportを変換
        data['dsport'] = data['dsport'].apply(self.convert_to_decimal)
        # dsportの値が-1の行（すなわち、無効な値を含む行）を削除し、その数をカウント
        n_invalid_dsport = len(data[data['dsport'] == -1])
        data = data[data['dsport'] != -1]
        print(f'Invalid dsport: {n_invalid_dsport}')

        # sportに含まれる文字列を削除
        is_int = data['sport'].apply(lambda x: isinstance(x, int))
        data = data[is_int]

        # dstip, srcipをbitwiseに変換
        #data = self.bitwise(data) # デバッグのためにコメントアウト

        #srcipを出現率が高い順から20個ずつ取得する
        srcip = data['srcip'].value_counts().index[:20]
        #srcipを含む行のみを抽出
        data = data[data['srcip'].isin(srcip)]

        data = data.reset_index() 

        return data

    def cut_data(self, data):
        data = data.copy()
        nrows = min(self.nrows, data.shape[0]) # 行数がnrowsよりも少ない場合は、dataをそのまま返す
        if self.config['fix_imbalance']: # 不均衡データを均衡データにする場合
            data_0 = data[data['Label'] == 0]
            data_1 = data[data['Label'] == 1]
            half_nrows = nrows // 2
            data = pd.concat([data_0.iloc[:half_nrows], data_1.iloc[:half_nrows]])
        else: # 不均衡データのまま
            data = data.iloc[:nrows]
        return data

    def load_data(self):
        self.data = pd.read_csv(self.DATA_FILE_PATH)
        features = pd.read_csv(self.DATA_FEATURES_FILE_PATH, index_col='No.')
        features = features['Name']
        self.data.columns = features
        self.data = self.cut_data(self.data)

        self.data = self.preprocess(self.data) 
        self.labels = self.data['Label'] # Pandas Series
        self.data = self.data.drop(columns=['Label']) # Pandas DataFrame

    def get_data(self):
        return self.X_train, self.X_test, self.y_train, self.y_test, self.config

        



