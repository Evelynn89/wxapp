Page({
  data: {
    buildings: [] // 存储建筑物的信息，包括 image_url 和 type
  },

  onLoad: function() {
    this.fetchBuildings();
  },

  // 添加建筑物类型的映射
  typeMapping: {
    1: '宗教建筑',
    2: '政府部门建筑',
    3: '商业建筑',
    4: '文化与教育建筑',
    5: '工业与交通建筑',
    6: '旧址建筑',
    7: '历史建筑'
  },

  fetchBuildings: function() {
    wx.request({
      url: 'http://10.37.74.224:5000/buildings', // 使用局域网 IP 地址
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200) {
          console.log(res.data); // 打印返回的数据
          
          // 拼接完整的图片 URL 并转换 type 字段为对应的文本
          const updatedBuildings = res.data.map(building => ({
            ...building,
            image_url: `http://10.37.74.224:5000${building.image_url}`, // 拼接完整的图片 URL
            type_text: this.typeMapping[building.type] || '未知类型' // 根据 type 映射为描述文本
          }));

          this.setData({
            buildings: updatedBuildings
          });
        } else {
          console.error('请求失败', res);
        }
      },
      fail: (err) => {
        console.error('请求错误', err);
      }
    });
  },

  goToIntroduction: function(e) {
    const buildingId = e.currentTarget.dataset.id; // 获取点击的建筑物 ID
    getApp().globalData.buildingId = buildingId;
    wx.navigateTo({
      url: `/pages/introduction/introduction?id=${buildingId}`
    });
  }
});
