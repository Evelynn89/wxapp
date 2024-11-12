const app = getApp(); // 获取应用实例
Page({
  data: {
    id: '',
    name: '',
    address: '',
    des: '',
    guide: '',
    url: '', // 存储完整的图片 URL
    question: '',
    formattedContent: {}  // 用于存储 towxml 转换后的数据
  },

  onLoad: function(options) {
    const buildingId = options.id;
    this.fetchBuildingDetails(buildingId);
  },

  fetchBuildingDetails: function(id) {
    wx.request({
      url: `http://10.197.235.234:5000/buildings/${id}`, // 使用局域网 IP 地址来查询详情
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200) {
          // 拼接完整的图片 URL
          const imageUrl = `http://10.197.235.234:5000${res.data.image_url1}`;

          this.setData({
            id: res.data.id,
            name: res.data.name,
            address: res.data.address,
            des: res.data.des,
            guide: res.data.guide,
            url: imageUrl // 使用完整的图片 URL
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

  // 用户输入框变动
  onInputChange: function (e) {
    this.setData({
      question: e.detail.value
    });
  },

  // 提交问题并获取回答
  submitQuestion: function () {
    const question = this.data.question;

    // 如果问题为空，提醒用户
    if (!question) {
      wx.showToast({
        title: '请输入问题',
        icon: 'none'
      });
      return;
    }

    // 显示加载中动画
  wx.showLoading({
    title: '正在生成回答...',
    mask: true
  });

    wx.request({
      url: 'http://10.197.235.234:5000/chat',
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: {
        question: question
      },
      success: (res) => {
        wx.hideLoading();
        if (res.statusCode === 200 && res.data.reply) {
          // 使用 towxml 将 Markdown 转换为小程序富文本格式
          const formatted = app.towxml.toJson(res.data.reply, 'markdown');
          this.setData({
            formattedContent: formatted
          });
        } else {
          this.setData({
            formattedContent: app.towxml.toJson('未能获取回答', 'markdown')
          });
        }
      },
      fail: (err) => {
         wx.hideLoading();
        console.error('请求失败', err);
        this.setData({
          formattedContent: app.towxml.toJson('请求失败，请检查网络连接', 'markdown')
        });
      }
    });
  },


  // 点击地图 marker 时跳转到地图页
  onMarkerTap(event) {
    const markerId = event.markerId;  // 这是点击时返回的 marker 的 index
    wx.navigateTo({
      url: `/pages/map/map?id=${markerId}` // 跳转到地图页面，并传递 ID
    });
  },

  // 点击按钮跳转到位置页面
  goToLocation(event) {
    const id = event.currentTarget.dataset.id; // 使用按钮绑定的数据 ID
    wx.navigateTo({
      url: `/pages/map/map?id=${id}` // 跳转到地图页面，并传递建筑物 ID
    });
  },

  // 点击按钮跳转到周边游玩推荐页面
  goToNeighbor(event) {
    const id = event.currentTarget.dataset.id; // 使用按钮绑定的数据 ID
    wx.navigateTo({
      url: `/pages/recommendation/recommendation?id=${id}`
    });
  },

  navigateToQuestion(event) {
    const buildingId = event.currentTarget.dataset.id;
    wx.navigateTo({
      url: `/pages/question/question?id=${buildingId}`, // 使用id作为参数
      success: () => {
        console.log('Successfully navigated to quiz page');
      },
      fail: (err) => {
        console.error('Failed to navigate to quiz page', err);
      }
    });
  }
});
