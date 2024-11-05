import pymysql
import math

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'architecture'
}


# 获取数据库连接
def get_db_connection():
    return pymysql.connect(**db_config)


# 计算两个经纬度之间的距离（使用 Haversine 公式）
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # 地球半径，单位为公里
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
