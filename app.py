from flask import Flask, jsonify, send_from_directory, request
import pymysql
import requests
import math
import random

from flask_cors import CORS

from mysql import get_db_connection
from image_detection import upload_photo

app = Flask(__name__)
CORS(app)

# 提供静态文件的路由，允许访问静态文件目录
@app.route('/static/<path:filename>', methods=['GET'])
def serve_static(filename):
    return send_from_directory('static', filename)

# 高德地图 API 地理编码函数
def geocode_address(address):
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT latitude, longitude FROM info WHERE address = %s", (address,))
    result = cursor.fetchone()

    if result and result['latitude'] is not None and result['longitude'] is not None:
        print(f"Address '{address}' found in cache.")
        return result['latitude'], result['longitude']

    api_key = 'f64f53bf957eb88ea272dc28e695201f'  # 替换为你的高德地图 API Key
    url = f'https://restapi.amap.com/v3/geocode/geo?address={address}&key={api_key}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"Response for address '{address}': {data}")

        if 'geocodes' in data and data['geocodes']:
            for result in data['geocodes']:
                if result['level'] == '门址':
                    location = result['location'].split(',')
                    lat, lon = float(location[1]), float(location[0])
                    cursor.execute("UPDATE info SET latitude = %s, longitude = %s WHERE address = %s",
                                   (lat, lon, address))
                    connection.commit()
                    cursor.close()
                    connection.close()
                    return lat, lon

            location = data['geocodes'][0]['location'].split(',')
            lat, lon = float(location[1]), float(location[0])
            cursor.execute("UPDATE info SET latitude = %s, longitude = %s WHERE address = %s", (lat, lon, address))
            connection.commit()
            cursor.close()
            connection.close()
            return lat, lon
        else:
            print(f"Geocoding failed for address: {address}. Response data: {data}")
    else:
        print(f"Request failed with status code {response.status_code} for address: {address}")

    cursor.close()
    connection.close()
    return None

# 获取建筑信息并返回经纬度
@app.route('/buildings', methods=['GET'])
def get_buildings():
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT id, name, address, latitude, longitude, image_url, image_url1 FROM info")
    buildings = cursor.fetchall()

    for building in buildings:
        if building['latitude'] is None or building['longitude'] is None:
            coords = geocode_address(building['address'])
            if coords:
                building['latitude'], building['longitude'] = coords
            else:
                building['latitude'], building['longitude'] = None, None

    cursor.close()
    connection.close()
    return jsonify(buildings)

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

# 更新每个建筑的临近建筑
@app.route('/update_neighbors', methods=['POST'])
def update_neighbors():
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute(
        "SELECT id, name, latitude, longitude FROM info WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    buildings = cursor.fetchall()

    for building in buildings:
        distances = []
        for other_building in buildings:
            if building['id'] != other_building['id']:
                distance = haversine(building['latitude'], building['longitude'],
                                     other_building['latitude'], other_building['longitude'])
                distances.append((other_building['id'], distance))

        top_5_neighbors = sorted(distances, key=lambda x: x[1])[:5]

        cursor.execute("DELETE FROM neighbor WHERE id = %s", (building['id'],))
        for neighbor_id, _ in top_5_neighbors:
            cursor.execute("INSERT INTO neighbor (id, neighbor_id) VALUES (%s, %s)",
                           (building['id'], neighbor_id))

    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({'message': 'Neighbor information updated successfully'})

# 获取单个建筑的详细信息
@app.route('/buildings/<int:id>', methods=['GET'])
def get_building_by_id(id):
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute(
        "SELECT id, name, address, des, guide, latitude, longitude, image_url, image_url1 FROM info WHERE id = %s",
        (id,))
    building = cursor.fetchone()

    if building:
        if building['latitude'] is None or building['longitude'] is None:
            coords = geocode_address(building['address'])
            if coords:
                building['latitude'], building['longitude'] = coords
            else:
                building['latitude'], building['longitude'] = None, None

        response = jsonify(building)
    else:
        response = jsonify({"error": "Building not found"}), 404

    cursor.close()
    connection.close()

    return response

# 获取邻近建筑信息
@app.route('/neighbors/<int:id>', methods=['GET'])
def get_neighbors(id):
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT neighbor_id FROM neighbor WHERE id = %s", (id,))
    neighbor_ids = cursor.fetchall()

    neighbor_id_list = [n['neighbor_id'] for n in neighbor_ids]

    if neighbor_id_list:
        cursor.execute(
            "SELECT id, name, address, image_url FROM info WHERE id IN (%s)" % ','.join(['%s'] * len(neighbor_id_list)),
            neighbor_id_list)
        neighbors = cursor.fetchall()
    else:
        neighbors = []

    cursor.close()
    connection.close()

    return jsonify(neighbors)

# 获取随机建筑信息
@app.route('/random_buildings', methods=['GET'])
def get_random_buildings():
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT id FROM info")
    all_building_ids = cursor.fetchall()

    random_ids = random.sample([b['id'] for b in all_building_ids], 3) if len(all_building_ids) >= 3 else [b['id'] for b in all_building_ids]

    cursor.execute(
        "SELECT id, name, address, image_url FROM info WHERE id IN (%s)" % ','.join(['%s'] * len(random_ids)),
        random_ids)
    random_buildings = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(random_buildings)

@app.route('/upload_photo', methods=['POST'])
def handle_upload_photo():
    return upload_photo()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)




