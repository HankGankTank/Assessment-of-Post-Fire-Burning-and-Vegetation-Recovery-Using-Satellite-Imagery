import streamlit as st
import pandas as pd
import requests
import io
import json
import hmac
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib import font_manager
import folium
from streamlit_folium import st_folium
from google.oauth2 import service_account

# 必须使用 foliumap 才能在 Streamlit 中完美渲染
import ee


# --- 自定义函数：将 GEE 图层直接加到原生 Folium 地图上 (升级版) ---
def add_ee_layer(self, ee_image_object, vis_params, name, show=True):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Map Data &copy; Google Earth Engine',
        name=name,
        overlay=True,
        control=True,
        show=show  # 控制图层一开始是否默认勾选显示
    ).add_to(self)

# 将这个方法绑定到 Folium 的核心类上
folium.Map.add_ee_layer = add_ee_layer

# ==========================================
# 中英文界面翻译字典
# ==========================================
# 所有用户可见文字尽量通过 tr() 获取。遥感计算变量、GEE 波段名和
# session_state key 保持不变，因此切换语言不会改变或清空分析结果。
TRANSLATIONS = {
    "zh": {
        "title": "野火遥感与生态恢复监测面板",
        "author": "**作者:** Linghan Qi | 基于 NASA FIRMS 与 Google Earth Engine",
        "gee_init_error": "GEE 初始化失败：{error}。在 Streamlit Cloud 中请配置 GEE_SERVICE_ACCOUNT_JSON。",
        "access_title": "访问验证",
        "access_help": "请输入网站访问密钥。验证通过后才会加载地图和数据分析功能。",
        "access_key_label": "网站访问密钥",
        "unlock": "验证并进入",
        "invalid_access_key": "访问密钥不正确，请重试。",
        "access_not_configured": "网站尚未配置 APP_ACCESS_KEY。请先在 Streamlit Secrets 中添加该密钥。",
        "logout": "退出访问",
        "settings": "参数配置",
        "map_key": "NASA FIRMS MAP_KEY",
        "bbox": "研究区域 (BBOX)",
        "fire_start": "起火日期",
        "fire_end": "火灭日期",
        "bbox_numbers": "BBOX 必须由四个数字组成。",
        "bbox_format": "BBOX 格式应为 west,south,east,north。",
        "bbox_longitude": "经度必须满足 -180 ≤ west < east ≤ 180。",
        "bbox_latitude": "纬度必须满足 -90 ≤ south < north ≤ 90。",
        "bbox_error": "研究区域参数错误：{error}",
        "date_error": "起火日期不能晚于火灭日期。",
        "firms_tab": "NASA FIRMS 火点数据",
        "dnbr_tab": "烧伤严重度 (dNBR)",
        "ndvi_map_tab": "植被恢复时序地图",
        "ndvi_chart_tab": "NDVI 恢复轨迹分析",
        "firms_subheader": "历史火灾热异常点提取",
        "fetch_firms": "获取 FIRMS 数据",
        "map_key_required": "请在侧边栏输入 FIRMS MAP_KEY，或在 Streamlit Secrets 中配置 FIRMS_MAP_KEY。",
        "fetching_firms": "正在向 NASA 批量请求数据...",
        "firms_network_error": "{date}：网络或 HTTP 错误：{error}",
        "firms_csv_error": "{date}：CSV 解析错误：{error}",
        "firms_missing_fields": "NASA 响应缺少必要的火点字段。",
        "firms_success": "成功获取 {count} 条火点记录！",
        "download_csv": "下载 CSV 数据",
        "firms_no_data": "该时间段及区域内未检测到有效火点。",
        "s2_no_images": "{start} 至 {end} 没有满足云量条件的 Sentinel-2 影像。",
        "baseline_error": "无法建立火前/火后基线：{error}",
        "baseline_count": "Sentinel-2 基线影像：火前 {pre} 景，火后 {post} 景",
        "dnbr_subheader": "烧伤区域逐月 dNBR 变化（1-12 个月）",
        "dnbr_caption": "固定火前基线：{start} 至 {end}；每个火后图层为连续 30 天中值影像与该基线的差值。",
        "water_mask": "应用水体掩膜 (JRC)",
        "burned_only": "仅显示火烧迹地 (dNBR > 0.1)",
        "months_track": "火后跟踪月数",
        "generate_dnbr": "生成逐月 dNBR 地图",
        "generating_dnbr": "正在从 GEE 生成 {count} 个逐月 dNBR 图层...",
        "month_no_image": "火后第 {month} 月没有满足条件的 Sentinel-2 影像，已跳过。",
        "dnbr_layer": "火后第 {month} 月 dNBR ({start} ~ {end})",
        "dnbr_no_layers": "所选时间范围内没有可用于绘制逐月 dNBR 的影像。",
        "dnbr_legend": "#### dNBR 严重度 / 恢复图例",
        "recovery_significant": "显著恢复 (< -0.25)",
        "recovery_slight": "轻微恢复 (-0.25 至 -0.1)",
        "unburned": "未烧伤/无显著变化 (-0.1 至 0.1)",
        "burn_low": "低度烧伤 (0.1 至 0.27)",
        "burn_moderate_low": "中低度烧伤 (0.27 至 0.44)",
        "burn_moderate_high": "中高度烧伤 (0.44 至 0.66)",
        "burn_high": "高度烧伤 (> 0.66)",
        "dnbr_tip": "右上角图层控制器中每次只勾选一个月份，可逐月比较固定火烧迹地内的 dNBR 变化。绿色表示相对火前基线出现恢复，黄—紫色表示仍有不同程度的烧伤信号。",
        "dnbr_prompt": "点击上方按钮生成火后逐月 dNBR 交互地图。",
        "ndvi_map_subheader": "过火区域植被恢复空间演变（1-12 个月）",
        "generate_ndvi_map": "生成 NDVI 恢复时序地图",
        "generating_ndvi_map": "正在生成植被恢复时序地图（需在云端提取连续多期影像，请耐心等待 1-2 分钟）...",
        "ndvi_layer": "火后第 {month} 月烧伤区 NDVI ({start} ~ {end})",
        "ndvi_no_layers": "所选关键月份内没有可用于绘制 NDVI 地图的影像。",
        "ndvi_legend": "#### NDVI 植被健康度图例",
        "ndvi_negative": "严重烧伤/负 NDVI (< 0.0)",
        "ndvi_bare": "裸地 (0.0 至 0.2)",
        "ndvi_low": "低密度植被 (0.2 至 0.4)",
        "ndvi_medium": "中密度植被 (0.4 至 0.6)",
        "ndvi_dense": "高密度健康植被 (> 0.6)",
        "ndvi_map_tip": "*提示：在地图右上角切换第 1、3、6、9、12 月图层，观察灾区植被逐渐恢复的过程。*",
        "ndvi_map_prompt": "点击上方按钮生成 1-12 个月 NDVI 植被恢复时序交互地图。",
        "ndvi_chart_subheader": "NDVI 12 个月时序恢复轨迹模型",
        "run_ndvi_chart": "启动云计算生态韧性模型",
        "running_ndvi_chart": "正在提取连续 12 个月的灾区 NDVI 平均值，GEE 云计算可能需要 1-3 分钟...",
        "pre_ndvi_error": "火前 NDVI 基线计算失败：{error}",
        "month_no_ndvi": "火后第 {month} 月云掩膜后没有有效 NDVI 像元。",
        "month_ndvi_error": "火后第 {month} 月 NDVI 提取失败：{error}",
        "ndvi_trajectory": "火后 NDVI 恢复轨迹",
        "pre_baseline": "火前基线 ({value:.4f})",
        "chart_title": "火后植被恢复轨迹（12 个月）",
        "chart_x": "评估日期",
        "chart_y": "烧伤区域平均 NDVI",
        "chart_no_data": "数据获取失败，可能是该时间段云层遮挡严重。",
    },
    "en": {
        "title": "Wildfire Remote Sensing and Ecological Recovery Dashboard",
        "author": "**Author:** Linghan Qi | Powered by NASA FIRMS and Google Earth Engine",
        "gee_init_error": "GEE initialization failed: {error}. Configure GEE_SERVICE_ACCOUNT_JSON on Streamlit Cloud.",
        "access_title": "Access Verification",
        "access_help": "Enter the website access key. Mapping and data analysis will load only after verification.",
        "access_key_label": "Website Access Key",
        "unlock": "Verify and Continue",
        "invalid_access_key": "The access key is incorrect. Please try again.",
        "access_not_configured": "APP_ACCESS_KEY is not configured. Add it to Streamlit Secrets before using the app.",
        "logout": "Log Out",
        "settings": "Settings",
        "map_key": "NASA FIRMS MAP_KEY",
        "bbox": "Study Area (BBOX)",
        "fire_start": "Fire Start Date",
        "fire_end": "Fire End Date",
        "bbox_numbers": "BBOX must contain four numeric values.",
        "bbox_format": "BBOX format must be west,south,east,north.",
        "bbox_longitude": "Longitude must satisfy -180 ≤ west < east ≤ 180.",
        "bbox_latitude": "Latitude must satisfy -90 ≤ south < north ≤ 90.",
        "bbox_error": "Invalid study area: {error}",
        "date_error": "The fire start date cannot be later than the fire end date.",
        "firms_tab": "NASA FIRMS Fire Data",
        "dnbr_tab": "Burn Severity (dNBR)",
        "ndvi_map_tab": "Vegetation Recovery Maps",
        "ndvi_chart_tab": "NDVI Recovery Analysis",
        "firms_subheader": "Historical Fire Hotspot Extraction",
        "fetch_firms": "Fetch FIRMS Data",
        "map_key_required": "Enter a FIRMS MAP_KEY in the sidebar or configure FIRMS_MAP_KEY in Streamlit Secrets.",
        "fetching_firms": "Requesting batched data from NASA...",
        "firms_network_error": "{date}: Network or HTTP error: {error}",
        "firms_csv_error": "{date}: CSV parsing error: {error}",
        "firms_missing_fields": "The NASA response is missing required hotspot fields.",
        "firms_success": "Successfully retrieved {count} hotspot records.",
        "download_csv": "Download CSV Data",
        "firms_no_data": "No valid hotspots were detected in this area and time range.",
        "s2_no_images": "No Sentinel-2 imagery meeting the cloud threshold was found from {start} to {end}.",
        "baseline_error": "Unable to build the pre/post-fire baseline: {error}",
        "baseline_count": "Sentinel-2 baseline imagery: {pre} pre-fire scenes and {post} post-fire scenes",
        "dnbr_subheader": "Monthly dNBR Change Within the Burned Area (Months 1-12)",
        "dnbr_caption": "Fixed pre-fire baseline: {start} to {end}. Each post-fire layer compares a 30-day median composite with this baseline.",
        "water_mask": "Apply Water Mask (JRC)",
        "burned_only": "Show Burned Area Only (dNBR > 0.1)",
        "months_track": "Post-fire Months",
        "generate_dnbr": "Generate Monthly dNBR Map",
        "generating_dnbr": "Generating {count} monthly dNBR layers from GEE...",
        "month_no_image": "No qualifying Sentinel-2 imagery was found for post-fire month {month}; this month was skipped.",
        "dnbr_layer": "Post-Fire Month {month} dNBR ({start} to {end})",
        "dnbr_no_layers": "No imagery is available for monthly dNBR mapping in the selected period.",
        "dnbr_legend": "#### dNBR Severity / Recovery Legend",
        "recovery_significant": "Significant recovery (< -0.25)",
        "recovery_slight": "Slight recovery (-0.25 to -0.1)",
        "unburned": "Unburned/No significant change (-0.1 to 0.1)",
        "burn_low": "Low-severity burn (0.1 to 0.27)",
        "burn_moderate_low": "Moderate-low burn (0.27 to 0.44)",
        "burn_moderate_high": "Moderate-high burn (0.44 to 0.66)",
        "burn_high": "High-severity burn (> 0.66)",
        "dnbr_tip": "Select one month at a time in the layer control to compare dNBR within the fixed burned-area footprint. Green indicates recovery relative to the pre-fire baseline; yellow through purple indicates remaining burn signals.",
        "dnbr_prompt": "Click the button above to generate the monthly post-fire dNBR map.",
        "ndvi_map_subheader": "Spatial Vegetation Recovery Within the Burned Area (Months 1-12)",
        "generate_ndvi_map": "Generate NDVI Recovery Maps",
        "generating_ndvi_map": "Generating multi-period vegetation recovery layers from GEE. This may take 1-2 minutes...",
        "ndvi_layer": "Post-Fire Month {month} Burned-Area NDVI ({start} to {end})",
        "ndvi_no_layers": "No imagery is available for NDVI mapping in the selected key months.",
        "ndvi_legend": "#### NDVI Vegetation Health Legend",
        "ndvi_negative": "Severe burn/Negative NDVI (< 0.0)",
        "ndvi_bare": "Bare land (0.0 to 0.2)",
        "ndvi_low": "Low-density vegetation (0.2 to 0.4)",
        "ndvi_medium": "Medium-density vegetation (0.4 to 0.6)",
        "ndvi_dense": "Dense healthy vegetation (> 0.6)",
        "ndvi_map_tip": "*Tip: Switch among months 1, 3, 6, 9, and 12 in the layer control to observe vegetation recovery.*",
        "ndvi_map_prompt": "Click the button above to generate the 1-12 month NDVI recovery map.",
        "ndvi_chart_subheader": "12-Month NDVI Recovery Trajectory",
        "run_ndvi_chart": "Run Ecological Resilience Analysis",
        "running_ndvi_chart": "Extracting 12 months of mean burned-area NDVI. GEE processing may take 1-3 minutes...",
        "pre_ndvi_error": "Pre-fire NDVI baseline calculation failed: {error}",
        "month_no_ndvi": "No valid NDVI pixels remain after masking for post-fire month {month}.",
        "month_ndvi_error": "NDVI extraction failed for post-fire month {month}: {error}",
        "ndvi_trajectory": "Post-fire NDVI Trajectory",
        "pre_baseline": "Pre-fire Baseline ({value:.4f})",
        "chart_title": "Post-Fire Vegetation Recovery Trajectory (12 Months)",
        "chart_x": "Evaluation Date",
        "chart_y": "Mean NDVI Within Burned Area",
        "chart_no_data": "Data retrieval failed, possibly because of heavy cloud cover during the selected period.",
    }
}

# ==========================================
# 1. 页面配置与 GEE 初始化
# ==========================================
st.set_page_config(
    page_title="Wildfire Assessment",
    layout="wide",
    page_icon="🔥"
)

# 语言选择器必须位于其他界面组件之前。key 固定后，Streamlit 重运行时
# 会保留用户选择；计算按钮和地图的 session_state 不受语言切换影响。
language_option = st.sidebar.selectbox(
    "Language",
    ["English", "中文"],
    key="language_selector"
)
lang = "zh" if language_option == "中文" else "en"


def tr_for(language_code, key, **kwargs):
    """使用显式语言代码翻译文字，适合传入缓存函数。"""
    text = TRANSLATIONS[language_code].get(key, key)
    return text.format(**kwargs)


def tr(key, **kwargs):
    """按当前界面语言获取文字，并替换可选的格式化参数。"""
    return tr_for(lang, key, **kwargs)


def configure_chart_font(language_code):
    """中文界面下优先选择支持中文的本机字体，避免图表标题显示方框。"""
    if language_code != "zh":
        return

    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    preferred_fonts = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS"
    ]
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            break
    # 使用支持 Unicode 的减号，避免中文字体环境中坐标轴负号丢失。
    plt.rcParams["axes.unicode_minus"] = False


configure_chart_font(lang)
st.title(tr("title"))
st.markdown(tr("author"))

def get_secret(name, default=""):
    """读取 Streamlit Secret；本地未配置 secrets.toml 时返回默认值。"""
    try:
        # 本地开发时读取 .streamlit/secrets.toml；部署到 Streamlit Cloud 后
        # 会自动读取网页后台配置的同名 Secret，避免把密钥写进源代码。
        return st.secrets.get(name, default)
    except (FileNotFoundError, AttributeError):
        # 第一次本地运行可能尚未创建 secrets.toml，此时允许使用默认值。
        return default


def require_app_access():
    """在运行 GEE 或显示分析控件之前验证独立的网站访问密钥。"""
    # APP_ACCESS_KEY 只负责控制网页访问，不能复用 Google Cloud、GEE 或
    # NASA FIRMS 的 API 密钥。请仅在 Streamlit Secrets 中保存它。
    expected_key = str(get_secret("APP_ACCESS_KEY", ""))

    if not expected_key:
        # 默认采用“关闭访问”策略，避免忘记配置密钥时意外公开分析页面。
        st.error(tr("access_not_configured"))
        st.stop()

    # 验证结果只保存在当前 Streamlit 会话中；刷新或新建会话可能需要重新验证。
    if st.session_state.get("app_authenticated", False):
        if st.sidebar.button(tr("logout"), key="logout_button"):
            st.session_state["app_authenticated"] = False
            st.rerun()
        return

    st.subheader(tr("access_title"))
    st.info(tr("access_help"))

    # 使用 form，避免用户每输入一个字符就重新运行整个 Streamlit 脚本。
    with st.form("access_form", clear_on_submit=True):
        entered_key = st.text_input(
            tr("access_key_label"),
            type="password",
            key="access_key_input"
        )
        submitted = st.form_submit_button(tr("unlock"))

    if submitted:
        # compare_digest 避免普通字符串比较产生可测量的逐字符时间差。
        if hmac.compare_digest(entered_key, expected_key):
            st.session_state["app_authenticated"] = True
            st.rerun()
        else:
            st.error(tr("invalid_access_key"))

    # 未验证时在此停止：下面的 GEE 初始化、侧边栏参数、地图和数据都不会运行。
    st.stop()


require_app_access()


gee_project_id = get_secret("GEE_PROJECT_ID", "final-research-lq-gis")
gee_service_account_json = get_secret("GEE_SERVICE_ACCOUNT_JSON", "")


@st.cache_resource
def init_gee(project_id, language_code, service_account_json):
    """本地使用已保存凭据，云端使用 Streamlit Secret 中的服务账号。"""
    try:
        if service_account_json:
            # Streamlit Secrets 保存完整服务账号 JSON。这里只在内存中解析，
            # 不会把私钥写入文件系统或 GitHub 仓库。
            service_account_info = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=[
                    "https://www.googleapis.com/auth/earthengine",
                    "https://www.googleapis.com/auth/cloud-platform"
                ]
            )
            ee.Initialize(credentials=credentials, project=project_id)
        else:
            # 本地开发继续复用 earthengine authenticate 保存的用户凭据。
            ee.Initialize(project=project_id)
        return True
    except Exception as e:
        st.error(tr_for(language_code, "gee_init_error", error=e))
        return False

gee_ready = init_gee(
    gee_project_id,
    lang,
    gee_service_account_json
)

# ==========================================
# 2. 侧边栏：全局参数配置
# ==========================================
st.sidebar.header(tr("settings"))
map_key = st.sidebar.text_input(
    tr("map_key"),
    value=get_secret("FIRMS_MAP_KEY", ""),
    # password 只隐藏界面显示，不等于安全存储；真正的密钥放在 st.secrets 中。
    type="password",
    key="firms_map_key"
)
# BBOX 顺序固定为：最西经度、最南纬度、最东经度、最北纬度。
bbox_input = st.sidebar.text_input(
    tr("bbox"),
    value="-119.2,33.7,-117.8,34.5",
    key="bbox_input"
)

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input(
    tr("fire_start"),
    datetime(2025, 1, 7),
    key="fire_start_date"
)
end_date = col2.date_input(
    tr("fire_end"),
    datetime(2025, 1, 15),
    key="fire_end_date"
)

source = 'VIIRS_SNPP_SP'
offset_days = 30

# 将日期转换为字符串以便后续计算
start_date_str = start_date.strftime("%Y-%m-%d")
end_date_str = end_date.strftime("%Y-%m-%d")


def parse_bbox(bbox_text):
    """验证并返回 west, south, east, north 四个坐标。"""
    try:
        # strip() 允许用户在逗号前后输入空格。
        coords = [float(value.strip()) for value in bbox_text.split(',')]
    except ValueError as exc:
        raise ValueError(tr("bbox_numbers")) from exc

    if len(coords) != 4:
        raise ValueError(tr("bbox_format"))

    west, south, east, north = coords
    # 除了检查地理坐标范围，还必须保证 west < east、south < north，
    # 否则 Earth Engine 无法建立方向正确的矩形。
    if not (-180 <= west < east <= 180):
        raise ValueError(tr("bbox_longitude"))
    if not (-90 <= south < north <= 90):
        raise ValueError(tr("bbox_latitude"))
    return coords

# ==========================================
# 3. 核心计算函数 (带缓存优化)
# ==========================================
@st.cache_data(show_spinner=False)
def fetch_firms(map_key, source, bbox, start_dt_str, end_dt_str, language_code):
    """按 FIRMS API 的限制分批下载历史火点，并返回数据和错误列表。"""
    start_dt = datetime.strptime(start_dt_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_dt_str, "%Y-%m-%d")
    all_dfs = []
    errors = []
    current_start = start_dt
    
    while current_start <= end_dt:
        # FIRMS 的历史 _SP 数据一次最多请求 5 天，因此较长时间段必须分批。
        days_diff = (end_dt - current_start).days + 1
        day_range = min(5, days_diff)
        date_param = current_start.strftime("%Y-%m-%d")
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/{day_range}/{date_param}"
        
        try:
            # timeout 避免 NASA 服务无响应时让 Streamlit 页面永久等待。
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            df = pd.read_csv(io.StringIO(response.text))
            if not df.empty:
                all_dfs.append(df)
        except requests.RequestException as exc:
            errors.append(tr_for(
                language_code,
                "firms_network_error",
                date=date_param,
                error=exc
            ))
        except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
            errors.append(tr_for(
                language_code,
                "firms_csv_error",
                date=date_param,
                error=exc
            ))
        
        current_start += timedelta(days=day_range)
        # 主动降低请求频率，减少触发 FIRMS 429 限流的概率。
        time.sleep(1) # API 保护
        
    if all_dfs:
        # 把每个 1-5 天批次合并成一张表，再按位置和采集时间去重。
        final_df = pd.concat(all_dfs, ignore_index=True)
        required_columns = {'latitude', 'longitude', 'acq_date', 'acq_time'}
        if not required_columns.issubset(final_df.columns):
            errors.append(tr_for(language_code, "firms_missing_fields"))
            return pd.DataFrame(), errors
        return (
            final_df.drop_duplicates(
                subset=['latitude', 'longitude', 'acq_date', 'acq_time']
            ),
            errors
        )
    return pd.DataFrame(), errors

# ==========================================
# 4. 主体 UI 布局 (选项卡)
# ==========================================
if gee_ready:
    try:
        bbox_coords = parse_bbox(bbox_input)
    except ValueError as exc:
        st.error(tr("bbox_error", error=exc))
        st.stop()

    if start_date > end_date:
        st.error(tr("date_error"))
        st.stop()

    # 解析 GEE 几何和时间变量
    roi = ee.Geometry.BBox(*bbox_coords)
    
    # Earth Engine 的 filterDate 采用 [start, end)（结束日期不包含）区间。
    # 因此火后第一个 30 天窗口从“火灭日期的次日”开始。
    prefire_start = (start_date - timedelta(days=offset_days)).strftime("%Y-%m-%d")
    prefire_end = start_date_str
    postfire_start = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
    postfire_end = (end_date + timedelta(days=offset_days + 1)).strftime("%Y-%m-%d")
    
    # 建立多标签页
    tab1, tab2, tab3, tab4 = st.tabs([
        tr("firms_tab"),
        tr("dnbr_tab"),
        tr("ndvi_map_tab"),
        tr("ndvi_chart_tab")
    ])
    
    with tab1:
        st.subheader(tr("firms_subheader"))
        if st.button(tr("fetch_firms")):
            if not map_key:
                st.error(tr("map_key_required"))
            else:
                with st.spinner(tr("fetching_firms")):
                    fire_df, firms_errors = fetch_firms(
                        map_key,
                        source,
                        bbox_input,
                        start_date_str,
                        end_date_str,
                        lang
                    )
                for error_message in firms_errors:
                    st.warning(error_message)
                if not fire_df.empty:
                    st.success(tr("firms_success", count=len(fire_df)))
                    st.dataframe(fire_df)
                    
                    # 提供 CSV 下载按钮
                    csv = fire_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        tr("download_csv"),
                        data=csv,
                        file_name=f"firms_{start_date_str}.csv",
                        mime="text/csv"
                    )
                else:
                    st.warning(tr("firms_no_data"))

    # ----- GEE 通用计算变量初始化 -----
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")

    def add_nbr(image):
        """为单景影像增加 NBR 波段：NBR = (B8 - B12) / (B8 + B12)。"""
        # B8 是近红外，健康植被通常反射较强；B12 是短波红外，
        # 对植被含水量和火烧后干燥地表较敏感。
        return image.addBands(
            image.normalizedDifference(['B8', 'B12']).rename('NBR')
        )

    def get_ndvi(image):
        """计算 NDVI：B8 为近红外，B4 为红光。"""
        return image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    def mask_s2_clouds(image):
        """移除 Sentinel-2 SCL 中的无效、云影、云、卷云和冰雪像元。"""
        # SCL（Scene Classification Layer）是 Sentinel-2 L2A 自带的
        # 像元分类波段。它比只看整景云量更精细，可以逐像元去云。
        scl = image.select('SCL')

        # 需要屏蔽的 SCL 类别：
        # 0=无数据，1=饱和/坏像元，3=云影，7=低概率云/未分类，
        # 8=中概率云，9=高概率云，10=卷云，11=雪/冰。
        # 类别 2（暗像元）、4（植被）、5（裸地）、6（水体）暂时保留；
        # 水体会在后面用 JRC 数据进行更稳定的专门掩膜。
        invalid = (scl.eq(0)
            .Or(scl.eq(1))
            .Or(scl.eq(3))
            .Or(scl.eq(7))
            .Or(scl.eq(8))
            .Or(scl.eq(9))
            .Or(scl.eq(10))
            .Or(scl.eq(11)))

        # invalid 中 1 表示“需要删除”。Not() 将其反转为有效像元掩膜：
        # 1=保留、0=透明。updateMask 不删除波段，只使无效像元不参与计算。
        return image.updateMask(invalid.Not())

    def prepare_s2_collection(start_date_value, end_date_value):
        """按空间、日期、整景云量和 SCL 像元掩膜准备 Sentinel-2 集合。"""
        # 这里采用两级去云：
        # 1) CLOUDY_PIXEL_PERCENTAGE < 20：先排除整体云量过高的影像；
        # 2) map(mask_s2_clouds)：再从剩余影像中逐像元去除云和云影。
        return (s2.filterBounds(roi)
            # filterDate 是 [start, end) 左闭右开区间，不包含结束日期。
            .filterDate(start_date_value, end_date_value)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            # map() 让 Earth Engine 在服务端把函数应用到集合中的每景影像。
            .map(mask_s2_clouds))

    def get_median_composite(start_date_value, end_date_value,
                             with_nbr=False, allow_empty=False):
        """返回一个时间窗口的中值合成影像及源影像数量。"""
        # 此处得到的仍是 ee.ImageCollection；Earth Engine 采用惰性计算，
        # 在真正请求结果之前大部分操作只是构建服务端计算表达式。
        collection = prepare_s2_collection(start_date_value, end_date_value)

        # size() 返回服务端 ee.Number；getInfo() 才把数量同步取回 Python。
        # 这会产生一次网络请求，但能避免对空集合执行 median/select 后报错。
        image_count = int(collection.size().getInfo())
        if image_count == 0:
            if allow_empty:
                # 月度循环允许某个月无影像：返回 None，让调用处跳过该月。
                return None, 0
            # 火前/首个火后基线不能为空，否则 dNBR 没有计算基础。
            raise RuntimeError(
                tr(
                    "s2_no_images",
                    start=start_date_value,
                    end=end_date_value
                )
            )
        if with_nbr:
            # 先对每景影像计算 NBR，再对 NBR 求中值；这与先合成 B8/B12
            # 再计算 NBR 并不完全等价，当前做法表示窗口内 NBR 的中位状态。
            collection = collection.map(add_nbr)

        # median() 对每个像元、每个波段求中位数，能降低残云和异常值影响；
        # clip(roi) 最后把输出限制在研究区域内。
        return collection.median().clip(roi), image_count

    try:
        # 火前基线：起火日前 30 天；火后基线：火灭次日起连续 30 天。
        # 两个窗口都必须存在影像，因此这里保留 allow_empty=False 默认值。
        pre_fire_img, pre_image_count = get_median_composite(
            prefire_start,
            prefire_end,
            with_nbr=True
        )
        post_fire_img, post_image_count = get_median_composite(
            postfire_start,
            postfire_end,
            with_nbr=True
        )
    except Exception as exc:
        st.error(tr("baseline_error", error=exc))
        st.stop()

    st.sidebar.caption(
        tr(
            "baseline_count",
            pre=pre_image_count,
            post=post_image_count
        )
    )
    
    # dNBR = 火前 NBR - 火后 NBR。正值越大通常表示烧伤越严重；
    # 随植被恢复，后续月份的 dNBR 通常会逐渐降低。
    dnbr = pre_fire_img.select('NBR').subtract(
        post_fire_img.select('NBR')
    ).rename('dNBR')
    
    # LSIB 用于裁掉海洋；JRC max_extent=0 表示该像元未被记录为历史水体。
    land_boundaries = ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
    inland_water_mask = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('max_extent').eq(0)
    
    def classify_dnbr(dnbr_image):
        """按照 USGS/FIREMON 阈值将连续 dNBR 重分类为 1-7 级。"""
        # where() 按顺序把每个连续 dNBR 像元赋为离散类别：
        # 1-2=恢复信号，3=无显著变化，4-7=低到高烧伤严重度。
        return (ee.Image(0)
            .where(dnbr_image.lt(-0.25), 1)
            .where(dnbr_image.gte(-0.25).And(dnbr_image.lt(-0.1)), 2)
            .where(dnbr_image.gte(-0.1).And(dnbr_image.lt(0.1)), 3)
            .where(dnbr_image.gte(0.1).And(dnbr_image.lt(0.27)), 4)
            .where(dnbr_image.gte(0.27).And(dnbr_image.lt(0.44)), 5)
            .where(dnbr_image.gte(0.44).And(dnbr_image.lt(0.66)), 6)
            .where(dnbr_image.gte(0.66), 7)
            # 保留输入影像原有掩膜，防止无数据区域被常数 0 填充。
            .updateMask(dnbr_image.mask()))

    # 先保留连续 dNBR，再从连续值创建 dNBR > 0.1 的固定火烧迹地掩膜。
    # 原代码使用分类图像 .gt(4)，会错误排除第 4 类（0.1-0.27）的低度烧伤。
    dnbr_land = dnbr.clipToCollection(land_boundaries)
    dnbr_clean = dnbr_land.updateMask(inland_water_mask)
    # 分类影像只用于颜色显示；固定烧伤掩膜必须从连续 dNBR 创建，
    # 不能把 1-7 分类编号误当作真实 dNBR 数值。
    classified_dnbr = classify_dnbr(dnbr)
    dnbr_no_water = classify_dnbr(dnbr_clean)
    burned_mask = dnbr_clean.gt(0.1)
    burned_area_only = dnbr_no_water.updateMask(burned_mask)
    
    # 可视化字典
    vis_dnbr = {'min': 1, 'max': 7, 'palette': ['006400', '90EE90', 'E0E0E0', 'FFFF00', 'FFA500', 'FF0000', '800080']}
    vis_burned_only = {'min': 4, 'max': 7, 'palette': ['ffff00', 'ffA500', 'ff0000', '800080']}
    vis_ndvi = {'min': 0.0, 'max': 0.8, 'palette': ['A52A2A', 'FFA500', 'FFFF00', '00FF00', '008000']}

    legend_dnbr_full = {
        tr("recovery_significant"): "006400",
        tr("recovery_slight"): "90EE90",
        tr("unburned"): "E0E0E0",
        tr("burn_low"): "FFFF00",
        tr("burn_moderate_low"): "FFA500",
        tr("burn_moderate_high"): "FF0000",
        tr("burn_high"): "800080"
    }

    with tab2:
        st.subheader(tr("dnbr_subheader"))
        st.caption(
            tr(
                "dnbr_caption",
                start=prefire_start,
                end=(start_date - timedelta(days=1)).strftime('%Y-%m-%d')
            )
        )

        # 交互开关控制（前端 UI 控制后台逻辑）
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 1])
        use_water_mask = col_ctrl1.checkbox(
            tr("water_mask"),
            value=True,
            key="use_water_mask"
        )
        show_burned_only = col_ctrl2.checkbox(
            tr("burned_only"),
            value=True,
            key="show_burned_only"
        )
        months_to_track = col_ctrl3.slider(
            tr("months_track"),
            1,
            12,
            12,
            key="months_to_track"
        )

        if "show_dnbr_map" not in st.session_state:
            st.session_state.show_dnbr_map = False

        if st.button(tr("generate_dnbr"), key="render_dnbr"):
            st.session_state.show_dnbr_map = True

        if st.session_state.show_dnbr_map:
            with st.spinner(tr("generating_dnbr", count=months_to_track)):
                coords = [float(x) for x in bbox_input.split(',')]
                center_lat = (coords[1] + coords[3]) / 2
                center_lon = (coords[0] + coords[2]) / 2

                m_dnbr = folium.Map(location=[center_lat, center_lon], zoom_start=10)

                # 火烧迹地范围固定取自火后第一个 30 天窗口。后续月份即使
                # dNBR 下降为灰色或绿色，也仍在同一受灾范围内显示，便于比较恢复。
                fixed_burned_mask = dnbr_land.gt(0.1)
                if use_water_mask:
                    fixed_burned_mask = fixed_burned_mask.updateMask(inland_water_mask)

                loaded_dnbr_layers = 0
                for i in range(months_to_track):
                    # 第 1 月：火灭次日起第 1-30 天；第 2 月：第 31-60 天，以此类推。
                    period_start_dt = end_date + timedelta(days=1 + i * offset_days)
                    # 结束日期专门多加 30 天，因为 filterDate 不包含结束日。
                    period_end_exclusive_dt = period_start_dt + timedelta(days=offset_days)
                    # 图层标题展示人类习惯的闭区间，因此再减 1 天。
                    period_end_inclusive_dt = period_end_exclusive_dt - timedelta(days=1)

                    period_start_str = period_start_dt.strftime("%Y-%m-%d")
                    period_end_str = period_end_exclusive_dt.strftime("%Y-%m-%d")
                    recovery_img, recovery_count = get_median_composite(
                        period_start_str,
                        period_end_str,
                        with_nbr=True,
                        allow_empty=True
                    )
                    if recovery_img is None:
                        # 一个空月份不应导致整个 12 个月分析失败。
                        st.warning(tr("month_no_image", month=i + 1))
                        continue

                    # 所有月份都减去同一幅火前 NBR 基线，保证月份之间可比较。
                    monthly_dnbr = (pre_fire_img.select('NBR')
                        .subtract(recovery_img.select('NBR'))
                        .rename('dNBR'))
                    monthly_dnbr = monthly_dnbr.clipToCollection(land_boundaries)

                    if use_water_mask:
                        monthly_dnbr = monthly_dnbr.updateMask(inland_water_mask)
                    if show_burned_only:
                        # 固定空间范围，而不是每个月重新用 dNBR>0.1 筛选；
                        # 否则已经恢复的绿色像元会从地图中消失，无法观察恢复过程。
                        monthly_dnbr = monthly_dnbr.updateMask(fixed_burned_mask)

                    classified_monthly = classify_dnbr(monthly_dnbr)
                    layer_name = tr(
                        "dnbr_layer",
                        month=i + 1,
                        start=period_start_dt.strftime('%Y-%m-%d'),
                        end=period_end_inclusive_dt.strftime('%Y-%m-%d')
                    )
                    m_dnbr.add_ee_layer(
                        classified_monthly,
                        vis_dnbr,
                        layer_name,
                        # 若第 1 月为空，则让后面第一个有效月份默认显示。
                        show=(loaded_dnbr_layers == 0)
                    )
                    loaded_dnbr_layers += 1

                if loaded_dnbr_layers:
                    m_dnbr.add_child(folium.LayerControl(collapsed=False))
                    st_folium(
                        m_dnbr,
                        use_container_width=True,
                        height=600,
                        key="monthly_dnbr_map"
                    )
                else:
                    st.error(tr("dnbr_no_layers"))

                st.markdown(tr("dnbr_legend"))
                legend_cols = st.columns(len(legend_dnbr_full))
                for i, (label, color) in enumerate(legend_dnbr_full.items()):
                    with legend_cols[i]:
                        st.markdown(
                            f"<div style='background-color: #{color}; height: 15px; "
                            "border-radius: 3px; margin-bottom: 5px;'></div>",
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f"<span style='font-size: 11px; line-height: 1.1; "
                            f"display: block;'>{label}</span>",
                            unsafe_allow_html=True
                        )

                st.info(tr("dnbr_tip"))
        else:
            st.info(tr("dnbr_prompt"))

    with tab3:
        st.subheader(tr("ndvi_map_subheader"))
        if "show_ndvi_map" not in st.session_state:
            st.session_state.show_ndvi_map = False

        if st.button(tr("generate_ndvi_map"), key="generate_ndvi_map"):
            st.session_state.show_ndvi_map = True

        if st.session_state.show_ndvi_map:
            with st.spinner(tr("generating_ndvi_map")):
                coords = [float(x) for x in bbox_input.split(',')]
                center_lat = (coords[1] + coords[3]) / 2
                center_lon = (coords[0] + coords[2]) / 2
                
                # 创建纯净版 Folium 底图
                m_ndvi = folium.Map(location=[center_lat, center_lon], zoom_start=10)
                
                # 遍历设定的月份并添加到地图
                target_months = [1, 3, 6, 9, 12]
                loaded_ndvi_layers = 0
                for m in target_months:
                    # 与 dNBR 页面保持同一时间定义：第 1 月从火灭次日开始，
                    # 第 m 月从火灭后的第 1+(m-1)*30 天开始。
                    s_dt = end_date + timedelta(days=1 + (m - 1) * 30)
                    e_dt = s_dt + timedelta(days=30)
                    
                    # 提取该月的中值影像；结束日期不包含在 filterDate 中。
                    s_str = s_dt.strftime("%Y-%m-%d")
                    e_str = e_dt.strftime("%Y-%m-%d")
                    display_end_str = (e_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                    monthly_img, monthly_count = get_median_composite(
                        s_str,
                        e_str,
                        allow_empty=True
                    )
                    if monthly_img is None:
                        st.warning(tr("month_no_image", month=m))
                        continue
                    
                    # 计算 NDVI 并掩膜（保留火烧迹地区域且排除水体）
                    # burned_mask 来自首个火后窗口，因此所有 NDVI 月份使用
                    # 完全相同的空间范围，避免区域变化影响月份间比较。
                    clean_ndvi = get_ndvi(monthly_img).clipToCollection(land_boundaries).updateMask(inland_water_mask).updateMask(burned_mask)
                    
                    # 仅默认显示第一个月的图层，其余月份默认折叠，防止色彩混叠
                    is_shown = loaded_ndvi_layers == 0
                    
                    # 使用原生方法加载
                    layer_name = tr(
                        "ndvi_layer",
                        month=m,
                        start=s_str,
                        end=display_end_str
                    )
                    m_ndvi.add_ee_layer(
                        clean_ndvi,
                        vis_ndvi,
                        layer_name,
                        show=is_shown
                    )
                    loaded_ndvi_layers += 1
                
                # 添加图层切换控制器
                if loaded_ndvi_layers:
                    m_ndvi.add_child(folium.LayerControl())
                    st_folium(
                        m_ndvi,
                        use_container_width=True,
                        height=600,
                        key="monthly_ndvi_map"
                    )
                else:
                    st.error(tr("ndvi_no_layers"))
                
                # 3. 生成 Streamlit 原生高颜值 NDVI 图例
                st.markdown(tr("ndvi_legend"))
                legend_ndvi_full = {
                    tr("ndvi_negative"): "A52A2A",
                    tr("ndvi_bare"): "FFA500",
                    tr("ndvi_low"): "FFFF00",
                    tr("ndvi_medium"): "00FF00",
                    tr("ndvi_dense"): "008000"
                }
                
                legend_cols = st.columns(len(legend_ndvi_full))
                for i, (label, color) in enumerate(legend_ndvi_full.items()):
                    with legend_cols[i]:
                        st.markdown(f"<div style='background-color: #{color}; height: 15px; border-radius: 3px; margin-bottom: 5px;'></div>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size: 11px; line-height: 1.1; display: block;'>{label}</span>", unsafe_allow_html=True)
                
                st.markdown(tr("ndvi_map_tip"))

        else:
            st.info(tr("ndvi_map_prompt"))

    with tab4:
        st.subheader(tr("ndvi_chart_subheader"))
        if st.button(tr("run_ndvi_chart")):
            with st.spinner(tr("running_ndvi_chart")):
                
                # 计算灾前 Baseline
                # reduceRegion 对固定烧伤区域内所有有效像元求均值；scale=200
                # 用较粗分辨率换取更快、更稳定的区域统计，降低 GEE 超时概率。
                pre_ndvi = get_ndvi(pre_fire_img).updateMask(burned_mask)
                try:
                    pre_ndvi_val = pre_ndvi.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=roi,
                        scale=200,
                        maxPixels=1e10
                    ).get('NDVI').getInfo()
                except Exception as exc:
                    pre_ndvi_val = None
                    st.warning(tr("pre_ndvi_error", error=exc))
                
                dates_list, ndvi_values = [], []
                progress_bar = st.progress(0)
                
                for i in range(12):
                    # 每个统计点对应一个不重叠的 30 天窗口。
                    p_start_dt = end_date + timedelta(days=1 + i * 30)
                    p_end_dt = p_start_dt + timedelta(days=30)

                    p_start_str = p_start_dt.strftime("%Y-%m-%d")
                    p_end_str = p_end_dt.strftime("%Y-%m-%d")
                    monthly_img, monthly_count = get_median_composite(
                        p_start_str,
                        p_end_str,
                        allow_empty=True
                    )
                    if monthly_img is None:
                        st.warning(tr("month_no_image", month=i + 1))
                        progress_bar.progress((i + 1) / 12)
                        continue

                    monthly_ndvi = get_ndvi(monthly_img).updateMask(burned_mask)
                     
                    try:
                        # getInfo() 会把 GEE 服务端均值同步取回 Python，
                        # 因而这一步是整个 12 个月曲线中最耗时的部分之一。
                        val = monthly_ndvi.reduceRegion(reducer=ee.Reducer.mean(), geometry=roi, scale=200, maxPixels=1e10).get('NDVI').getInfo()
                        if val is not None:
                            dates_list.append(p_start_str)
                            ndvi_values.append(val)
                        else:
                            st.warning(tr("month_no_ndvi", month=i + 1))
                    except Exception as exc:
                        st.warning(tr("month_ndvi_error", month=i + 1, error=exc))
                    progress_bar.progress((i + 1) / 12)
                
                if ndvi_values:
                    # 绘制 Matplotlib 图表
                    fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
                    df_ndvi = pd.DataFrame({'Date': pd.to_datetime(dates_list), 'NDVI': ndvi_values})
                    
                    ax.plot(
                        df_ndvi['Date'],
                        df_ndvi['NDVI'],
                        marker='o',
                        linestyle='-',
                        color='forestgreen',
                        linewidth=2.5,
                        label=tr("ndvi_trajectory")
                    )
                    if pre_ndvi_val is not None:
                        ax.axhline(
                            y=pre_ndvi_val,
                            color='red',
                            linestyle='--',
                            linewidth=2,
                            label=tr("pre_baseline", value=pre_ndvi_val)
                        )
                    
                    ax.set_title(tr("chart_title"), fontsize=14, fontweight='bold')
                    ax.set_xlabel(tr("chart_x"), fontsize=12)
                    ax.set_ylabel(tr("chart_y"), fontsize=12)
                    ax.grid(True, linestyle='--', alpha=0.6)
                    ax.legend(loc='lower right')
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    
                    # 在 Streamlit 中显示图表
                    st.pyplot(fig)
                    plt.close(fig)
                else:
                    st.error(tr("chart_no_data"))
