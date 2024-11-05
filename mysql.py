from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import pymysql
import os
import random
import math
import requests
import onnxruntime as ort
import numpy as np
import cv2
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # 允许跨域访问


# MySQL 配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'archilist'
}



# 获取数据库连接
def get_db_connection():
    return pymysql.connect(**db_config)

# 路由用于提供字体文件
@app.route('/assets/fonts/<path:filename>')
def serve_fonts(filename):
    font_directory = os.path.join(app.root_path, 'assets', 'fonts')
    return send_from_directory(font_directory, filename,mimetype='font/ttf')

# 提供静态文件的路由，允许访问静态文件目录
@app.route('/static/<path:filename>', methods=['GET'])
def serve_static(filename):
    return send_from_directory('static', filename)


# 高德地图 API 地理编码函数
def geocode_address(address):
    # 首先从数据库中检查是否已经缓存了该地址的经纬度
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # 查询缓存的经纬度
    cursor.execute("SELECT latitude, longitude FROM info WHERE address = %s", (address,))
    result = cursor.fetchone()

    if result and result['latitude'] is not None and result['longitude'] is not None:
        # 如果经纬度已经缓存，直接返回
        print(f"Address '{address}' found in cache.")
        return result['latitude'], result['longitude']

    # 如果没有缓存，调用高德 API 进行地理编码
    api_key = 'f64f53bf957eb88ea272dc28e695201f'  # 替换为你的高德地图 API Key
    url = f'https://restapi.amap.com/v3/geocode/geo?address={address}&key={api_key}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        print(f"Response for address '{address}': {data}")

        # 检查 'geocodes' 字段是否存在并非空，优先选择 '门址' 精度
        if 'geocodes' in data and data['geocodes']:
            for result in data['geocodes']:
                if result['level'] == '门址':
                    location = result['location'].split(',')
                    lat, lon = float(location[1]), float(location[0])
                    # 将地理编码结果缓存到数据库
                    cursor.execute("UPDATE info SET latitude = %s, longitude = %s WHERE address = %s",
                                   (lat, lon, address))
                    connection.commit()
                    cursor.close()
                    connection.close()
                    return lat, lon

            # 如果没有 '门址'，则选择第一个返回的结果
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

    # 关闭数据库连接
    cursor.close()
    connection.close()
    return None

# 获取建筑信息并返回经纬度
@app.route('/buildings', methods=['GET'])
def get_buildings():
    # 连接数据库
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # 查询 id, name, address, latitude, longitude, image_url, image_url1
    cursor.execute("SELECT id, name, address, latitude, longitude, image_url, image_url1 FROM info")
    buildings = cursor.fetchall()

    # 为每个建筑物获取经纬度
    for building in buildings:
        if building['latitude'] is None or building['longitude'] is None:
            # 如果没有经纬度，调用 geocode_address 获取
            coords = geocode_address(building['address'])
            if coords:
                building['latitude'], building['longitude'] = coords
            else:
                # 如果无法获取经纬度，设置默认值
                building['latitude'], building['longitude'] = None, None

    # 关闭数据库连接
    cursor.close()
    connection.close()

    # 返回 JSON 响应
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
    # 连接数据库
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # 查询所有建筑的经纬度信息
    cursor.execute("SELECT id, name, latitude, longitude FROM info WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    buildings = cursor.fetchall()

    # 遍历每个建筑，找到其最临近的 5 个建筑
    for building in buildings:
        distances = []
        for other_building in buildings:
            if building['id'] != other_building['id']:
                distance = haversine(building['latitude'], building['longitude'],
                                     other_building['latitude'], other_building['longitude'])
                distances.append((other_building['id'], distance))

        # 按距离排序，取前 5 个最近的建筑
        top_5_neighbors = sorted(distances, key=lambda x: x[1])[:5]

        # 将结果更新到 neighbor 表中
        cursor.execute("DELETE FROM neighbor WHERE id = %s", (building['id'],))
        for neighbor_id, _ in top_5_neighbors:
            cursor.execute("INSERT INTO neighbor (id, neighbor_id) VALUES (%s, %s)",
                           (building['id'], neighbor_id))

    # 提交更改并关闭连接
    connection.commit()
    cursor.close()
    connection.close()

    return jsonify({'message': 'Neighbor information updated successfully'})

# 获取单个建筑的详细信息
@app.route('/buildings/<int:id>', methods=['GET'])
def get_building_by_id(id):
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT id, name, address, des, guide, latitude, longitude, image_url, image_url1 FROM info WHERE id = %s", (id,))
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

@app.route('/random_buildings', methods=['GET'])
def get_random_buildings():
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    # 查询所有建筑的ID
    cursor.execute("SELECT id FROM info")
    all_building_ids = cursor.fetchall()

    # 随机选择4个建筑ID
    random_ids = random.sample([b['id'] for b in all_building_ids], 3) if len(all_building_ids) >= 3 else [b['id'] for b in all_building_ids]

    # 根据随机选中的ID获取建筑的详细信息
    cursor.execute("SELECT id, name, address, image_url FROM info WHERE id IN (%s)" % ','.join(['%s'] * len(random_ids)), random_ids)
    random_buildings = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(random_buildings)
# 获取邻近建筑信息
@app.route('/neighbors/<int:id>', methods=['GET'])
def get_neighbors(id):
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT neighbor_id FROM neighbor WHERE id = %s", (id,))
    neighbor_ids = cursor.fetchall()

    # 提取邻近建筑的ID列表
    neighbor_id_list = [n['neighbor_id'] for n in neighbor_ids]

    # 根据ID列表获取邻近建筑的详细信息
    if neighbor_id_list:
        cursor.execute("SELECT id, name, address, image_url FROM info WHERE id IN (%s)" % ','.join(['%s'] * len(neighbor_id_list)), neighbor_id_list)
        neighbors = cursor.fetchall()
    else:
        neighbors = []

    cursor.close()
    connection.close()

    return jsonify(neighbors)


UPLOAD_FOLDER = 'D:/backend/backend/static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 设置模型路径
model_path = 'D:/backend/backend/best.onnx'

# 加载 ONNX 模型
session = ort.InferenceSession(model_path)

# 预处理图像函数
def preprocess_image(image_path, img_size=640):
    img = cv2.imread(image_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (img_size, img_size))
    img = img.astype(np.float32) / 255.0  # 归一化
    img = np.transpose(img, (2, 0, 1))  # 转换为 (3, H, W)
    img = np.expand_dims(img, axis=0)  # 增加 batch 维度
    return img

# 查询数据库中的建筑信息
def get_building_info(building_id):
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            # 查询与 id 对应的建筑物信息
            cursor.execute("SELECT id, name, address, des, image_url FROM info WHERE id = %s", (building_id+1,))
            result = cursor.fetchone()
            return result if result else None
    finally:
        connection.close()

# 推理函数
def detect_objects(image_path):
    # 预处理图像
    input_image = preprocess_image(image_path)

    # 获取模型输入名称并进行推理
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_image})

    # 解析结果
    detections = []
    output = outputs[0]  # 获取第一个输出张量

    if len(output.shape) == 3 and output.shape[2] >= 6:
        output = output[0]  # 去掉 batch 维度
        for result in output:
            x1, y1, x2, y2, obj_conf = result[:5]
            class_scores = result[5:]
            class_id = np.argmax(class_scores)
            score = obj_conf * class_scores[class_id]
            if np.isscalar(score) and score > 0.7:  # 只处理置信度大于阈值的结果
                detections.append({
                    'box': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': float(score),
                    'id': int(class_id)  # 使用 id 而不是 class_id
                })

        # 使用 NMS 去除重叠框
        detections = apply_nms(detections, 0.5)

    return detections

# 非极大值抑制 (NMS) 函数
def apply_nms(detections, nms_threshold):
    if len(detections) == 0:
        return []

    boxes = np.array([d['box'] for d in detections])
    scores = np.array([d['confidence'] for d in detections])
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), score_threshold=0.0, nms_threshold=nms_threshold)

    if len(indices) > 0 and isinstance(indices[0], list):
        indices = [i[0] for i in indices]

    nms_detections = [detections[i] for i in indices]
    return nms_detections

# 上传照片并进行推理
@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        # 处理文件名并保存上传的图片
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # 调用模型进行推理
        detections = detect_objects(filepath)

        # 删除临时上传的图片
        os.remove(filepath)

        # 查询每个检测到的建筑物的详细信息
        for detection in detections:
            building_info = get_building_info(detection['id'])
            detection['building_info'] = building_info

        # 返回推理结果
        return jsonify({
            'message': 'Photo uploaded and analyzed successfully',
            'detections': detections
        }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
