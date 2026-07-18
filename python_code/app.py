import streamlit as st
import ee
import geemap.foliumap as geemap
import datetime
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. 页面与基础设置
# ---------------------------------------------------------
st.set_page_config(page_title="加州野火遥感监测系统", layout="wide")
st.title("🔥 加州野火遥感与生态恢复监测面板")
st.markdown("基于 NASA FIRMS 与 Google Earth Engine (Sentinel-2)")

# ---------------------------------------------------------
# 2. GEE 身份验证 (Streamlit 专用方式)
# ---------------------------------------------------------
# 使用 st.cache_resource 确保每次刷新网页只初始化一次 GEE
@st.cache_resource
def init_gee():
    try:
        # 在本地运行时，会自动读取你电脑上之前 earthengine authenticate 存下的凭证
        # 如果部署到云端，需要配置 Service Account Token
        ee.Initialize(project='your-gee-project-id') # 替换为你的项目 ID
        return True
    except Exception as e:
        st.error(f"GEE 初始化失败，请检查授权: {e}")
        return False

gee_ready = init_gee()

# ---------------------------------------------------------
# 3. 侧边栏：用户交互面板 (UI Controls)
# ---------------------------------------------------------
st.sidebar.header("⚙️ 参数配置")

# FIRMS API 设置
firms_key = st.sidebar.text_input("NASA FIRMS Map Key", type="password", help="输入你的 API Key")

# 空间范围设置 (BBOX)
bbox_input = st.sidebar.text_input("研究区域 (BBOX)", value="-124.4,32.5,-114.1,42.0")

# 时间范围设置
col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("起火日期", datetime.date(2025, 1, 7))
end_date = col2.date_input("火灭日期", datetime.date(2025, 1, 15))

# 分析模式选择
analysis_mode = st.sidebar.radio(
    "选择分析模块",
    ["NASA FIRMS 实时火点", "GEE 烧伤严重度 (dNBR)"]
)

# ---------------------------------------------------------
# 4. 核心功能逻辑与地图渲染
# ---------------------------------------------------------
if gee_ready:
    # 解析 BBOX
    coords = [float(x) for x in bbox_input.split(',')]
    roi = ee.Geometry.BBox(*coords)
    
    # 初始化底图
    m = geemap.Map(center=[(coords[1]+coords[3])/2, (coords[0]+coords[2])/2], zoom=7)
    
    # --- 模块 A: FIRMS 数据展示 ---
    if analysis_mode == "NASA FIRMS 实时火点":
        st.subheader("🛰️ VIIRS 活跃火点监测")
        if st.button("获取火点数据"):
            if not firms_key:
                st.warning("请在侧边栏输入 FIRMS API Key！")
            else:
                with st.spinner("正在向 NASA 请求数据..."):
                    # 这里接入你之前写好的 FIRMS requests 获取代码
                    # fetch_historical_firms_data(...) 
                    
                    # 占位：假设获取并清洗成功，转换为 DataFrame
                    st.success("数据获取成功！")
                    # m.add_points_from_xy(...) # 使用 geemap 将 Pandas 点位加入地图
                    
    # --- 模块 B: GEE dNBR 与水体掩膜 ---
    elif analysis_mode == "GEE 烧伤严重度 (dNBR)":
        st.subheader("🌍 灾后烧伤严重度分析 (双重水体掩膜)")
        
        with st.spinner("正在通过 GEE 云端计算 dNBR..."):
            # 日期处理
            prefire_start = (start_date - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            prefire_end = start_date.strftime("%Y-%m-%d")
            postfire_start = end_date.strftime("%Y-%m-%d")
            postfire_end = (end_date + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            
            def add_nbr(image):
                nbr = image.normalizedDifference(['B8', 'B12']).rename('NBR')
                return image.addBands(nbr)
            
            # 提取 S2 影像
            s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(roi)
            pre_fire_img = s2.filterDate(prefire_start, prefire_end).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).map(add_nbr).median().clip(roi)
            post_fire_img = s2.filterDate(postfire_start, postfire_end).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).map(add_nbr).median().clip(roi)
            
            # 计算 dNBR
            dnbr = pre_fire_img.select('NBR').subtract(post_fire_img.select('NBR')).rename('dNBR')
            
            # 双重水体掩膜 (调用你在 Colab 里的逻辑)
            land_boundaries = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
            jrc_water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('occurrence')
            inland_water_mask = jrc_water.unmask(0).lt(1)
            
            dnbr_clean = dnbr.clipToCollection(land_boundaries).updateMask(inland_water_mask)
            
            # 添加图层到地图
            vis_params = {'min': -0.25, 'max': 0.66, 'palette': ['green', 'yellow', 'orange', 'red', 'darkred']}
            m.addLayer(dnbr_clean, vis_params, 'dNBR (Masked)')
            m.addLayerControl()

    # ---------------------------------------------------------
    # 5. 在网页中渲染地图
    # ---------------------------------------------------------
    # 使用 geemap 专属的 Streamlit 渲染方法
    m.to_streamlit(height=600)