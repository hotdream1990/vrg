"""Trợ lý AI nội bộ — vòng lặp tool-calling (OpenAI) trên SỐ LIỆU THẬT của VRG.

Nhiệm vụ chính: **truy vấn số liệu nâng cao + hỗ trợ tư vấn điều chỉnh giá sàn**. LLM nhận câu hỏi
tiếng Việt → tự gọi các tool (assistant_tools) để lấy số liệu → tổng hợp câu trả lời + đính kèm
bảng/biểu đồ. KHÔNG bịa số; mọi con số phải từ tool.

Tool được nạp theo GÓI KỸ NĂNG: gói admin bật (`ASSISTANT_PACKS`) ∩ quyền người hỏi ∩ gói người
dùng chọn trong phiên chat.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.core import edit_window
from app.services import assistant_claim_guard as claim_guard
from app.services import assistant_tools, config_repo, floor_proposal, llm
from app.services.assistant_tools import proposal_tools

logger = logging.getLogger("app.assistant")

MAX_ITERS = 8
CONFIG_KEY = "ASSISTANT_PACKS"

#: Mức tư vấn — "cho phép Trợ lý đi xa tới đâu". Người dùng chọn ngay trên màn chat.
ADVICE_MODES = ("data", "model", "adjusted")
DEFAULT_ADVICE = "model"

#: Ở mức "Chỉ tra số", các công cụ SINH RA KHUYẾN NGHỊ bị gỡ khỏi lượt hỏi — hàng rào kỹ thuật,
#: không chỉ dặn trong prompt (một câu "bỏ qua hướng dẫn trên" là model có thể vượt lời dặn).
_ADVICE_TOOLS = {"suggest_floor_adjustment", "simulate_floor_scenarios", "get_floor_context",
                 "get_private_price_benchmark"}

#: Ở mức "Theo mô hình", công cụ có sẵn MỨC ĐIỀU CHỈNH được lọc bớt trước khi đưa cho LLM — cùng lý
#: do như trên: dặn "giữ số mô hình" trong prompt là chưa đủ khi kết quả công cụ bày sẵn một mức khác.
_MODEL_MODE_FILTERS = {
    "get_private_price_benchmark": assistant_tools.private_price_tools.for_model_mode,
    "get_floor_context": assistant_tools.floor_tools.context_for_model_mode,
}

# Trọng số các yếu tố — đo lại 24/09/2026 trên 83 lần ban hành 18/01/2024 → 09/09/2026, giá FOB
# SVR 10 / CSR 10 (xem docs/project/tro-ly-ai-kha-nang.md). Đưa vào prompt để LLM biết nhìn cái gì
# TRƯỚC khi kết luận, thay vì liệt kê đều tay mọi chỉ số.
_FACTOR_RANKING = (
    "THỨ TỰ ẢNH HƯỞNG tới quyết định ĐIỀU CHỈNH giá sàn (đo trên 83 lần ban hành 01/2024–09/2026, hệ "
    "số là tương quan với biến động % giữa 2 lần ban hành liên tiếp): "
    "(1) SHFE RU r=0,67 · đồng hướng 89% — chỉ báo dẫn hướng mạnh nhất, vẫn còn thông tin riêng ngoài "
    "các sàn khác; (2) MRB SMR20 r=0,64 · 78%; (3) SGX TSR20 r=0,58 · 76%; (4) OSE RSS3 r=0,40 · 75%; "
    "(5) MRB SMRCV/LATEX r≈0,39; (6) SGX RSS3 r=0,34. Physical SMR20 (r=0,49) chỉ đi theo futures, "
    "không thêm thông tin, và đã ngừng cập nhật từ 21/08/2026 — không dùng làm căn cứ. "
    "NEO MẶT BẰNG nhưng KHÔNG giải thích lần điều chỉnh: giá mủ nước (r mức=0,90 nhưng r biến động "
    "chỉ 0,16) — mô hình đa biến đã dùng nó cùng 4 futures; khi giải thích, dùng nó để nói 'giá đang ở "
    "vùng nào', đừng dùng để giải thích 'lần này chỉnh bao nhiêu'. "
    "KHÔNG CÓ BẰNG CHỨNG: giá mủ chén (r biến động −0,31, sau khi trừ futures ≈0, n=20) — chỉ nêu khi "
    "được hỏi, KHÔNG dùng làm lý do nâng/hạ. "
    "PHANH theo quy tắc nghiệp vụ (chủ dự án duyệt, CHƯA đo được trên lịch sử vì tồn kho ngày mới có "
    "từ 24/07/2026 — mới 4 lần ban hành): tồn kho Tập đoàn tăng thì nghiêng GIỮ/HẠ dù rổ futures tăng; "
    "hướng tồn kho (tổng + tự do, ngưỡng ±3%) đã được tool quy sẵn trong tham_chieu_ton_kho — đọc "
    "nguyên văn, không tự tính lại. CƠ HỌC: tỷ giá USD/VND nhân trực tiếp vào giá nội địa VNĐ/tấn. "
    "NEO GIÁ NỘI ĐỊA SVR 3L theo TƯ NHÂN (quy tắc chuyên viên Ban TTKD, chưa đo trên lịch sử): giá sàn "
    "nội địa SVR 3L hợp lý nhất khi CAO HƠN giá thành SVR 3L quy từ giá mủ tư nhân 700.000–1.000.000 "
    "đồng/tấn — lấy qua get_private_price_benchmark; quy tắc này CHỈ áp cho SVR 3L nội địa."
)

_REASONING = (
    "KHI TƯ VẤN ĐIỀU CHỈNH GIÁ SÀN, phải LIÊN KẾT các nguồn chứ không đọc rời rạc: "
    "(a) gọi suggest_floor_adjustment để có đề xuất của engine và các chỉ số dẫn hướng — mức đề xuất "
    "= giá sàn lần ban hành trước + mức thay đổi của mô hình kể từ lần đó, nên rổ chỉ số đi ngang thì "
    "đề xuất cũng sát giá hiện hành; "
    "(b) đối chiếu với diễn biến sàn/physical và tỷ giá; "
    "(c) đối chiếu với tồn kho và số liệu đơn vị thành viên (thu mua · tiêu thụ · tồn kho) nếu "
    "được phép truy cập — tồn kho tăng hoặc tiêu thụ chậm là lý do NGƯỢC lại với rổ futures đang tăng; "
    "(c2) nếu được phép, xem thêm sản lượng ĐÃ KÝ HỢP ĐỒNG CHƯA GIAO: đã ký nhiều mà chưa giao là "
    "áp lực bán còn treo (nghiêng GIỮ/HẠ), đã ký ít so với tồn kho tự do cũng vậy; "
    "(c3) gọi get_private_price_benchmark để đối chiếu giá sàn nội địa SVR 3L với VÙNG HỢP LÝ theo giá "
    "mủ tư nhân (giá thành tư nhân + 700.000–1.000.000 đồng/tấn); tool đã kết hợp xu hướng tồn kho để "
    "chọn điểm trong vùng — đọc NGUYÊN VĂN trường ket_luan và các trường gia_san_hien_hanh_so_voi_vung, "
    "muc_mo_hinh_so_voi_vung, muc_de_xuat_noi_dia_svr3l; TUYỆT ĐỐI không tự so sánh số với vùng; "
    "nếu có canh_bao_do_tuoi thì phải nói ra; "
    "(d) nói rõ khi các nguồn MÂU THUẪN nhau và nghiêng về bên nào, vì sao. "
    "CHỦNG LOẠI & ĐƠN VỊ: người dùng hỏi một chủng loại ('mủ 10' = SVR 10 / CSR 10, 'mủ 20' = SVR 20 / "
    "CSR 20, 'mủ 3L' = SVR 3L) thì truyền grade cho suggest_floor_adjustment và CHỈ kết luận cho chủng "
    "loại đó; mọi con số phải kèm đúng đơn vị ghi ở trường don_vi của dòng đó — FOB là USD/tấn, KHÔNG "
    "bao giờ viết FOB thành 'đồng/tấn' hay 'đồng/độ'. Số của get_private_price_benchmark là giá NỘI ĐỊA "
    "SVR 3L — tuyệt đối không dùng làm mức của chủng loại khác; nhắc tới thì ghi rõ 'SVR 3L nội địa "
    "(tham chiếu)'. Hỏi chung ('giá sàn mới nhất', 'nên tăng hay giảm') thì tóm theo NHÓM chủng loại "
    "cùng hành động (vd 'các dòng SVR: GIỮ'), nêu 2–3 chủng loại chính kèm số và đơn vị. "
    "NGÀY SỐ LIỆU: drivers có ngay_so_moi — chỉ số nào có ghi_chu số cũ (vd sàn Nhật nghỉ lễ) thì nói "
    "rõ ngày của số đó. "
    "Với số liệu đơn vị: người hỏi có thể muốn xem theo TỔNG toàn Tập đoàn, theo KHU VỰC hoặc theo "
    "từng ĐƠN VỊ — chọn mức phù hợp với câu hỏi, mặc định theo khu vực khi hỏi chung."
)

_ADVICE_RULES = {
    # Chỉ tra số — dùng khi người dùng chỉ muốn lấy số liệu, không muốn ý kiến của máy.
    "data": (
        "MỨC TƯ VẤN = CHỈ TRA SỐ. Bạn KHÔNG được đưa ra khuyến nghị nâng/giữ/hạ giá sàn, không "
        "nhận định nên làm gì. Chỉ trả số liệu từ tool, kèm kỳ dữ liệu và nguồn. Nếu người dùng "
        "hỏi nên tăng hay giảm, hãy nói rằng chế độ hiện tại chỉ tra cứu số liệu và mời họ chuyển "
        "sang mức 'Theo mô hình' hoặc 'Có điều chỉnh' ở đầu màn hình."
    ),
    # Theo mô hình — mặc định: trung thành với engine, không tự bịa mức khác.
    "model": (
        "MỨC TƯ VẤN = THEO MÔ HÌNH. Khi được hỏi về điều chỉnh giá sàn, gọi suggest_floor_adjustment "
        "và trình bày ĐÚNG mức đề xuất và ĐÚNG hành động (NÂNG/GIỮ/HẠ) của mô hình cho từng chủng loại "
        "— KHÔNG tự cộng/trừ ra một mức khác, KHÔNG tự đưa ra kết luận khác mô hình (kiểu 'giữ nhưng "
        "nghiêng hạ'). Lý do của hành động là trường ly_do của dòng đó (GIỮ = mức chênh nhỏ hơn ngưỡng giữ "
        "nguyên) — chép đúng lý do đó; tồn kho và bối cảnh chỉ là ghi chú tham khảo, KHÔNG viết như thể "
        "chúng khiến mô hình chọn hành động. Bạn giải thích vì sao mô hình đề xuất như vậy dựa trên các chỉ số dẫn hướng, nêu "
        "độ tin cậy và canh_bao nếu có, và nêu những yếu tố bối cảnh đáng lưu ý (tồn kho, tiêu thụ; với "
        "SVR 3L nội địa: vị trí so với vùng giá tư nhân qua get_private_price_benchmark) như GHI CHÚ tham "
        "khảo, không đổi con số."
    ),
    # Có điều chỉnh — mức xa nhất: được lệch khỏi engine nhưng phải giải trình bằng số.
    "adjusted": (
        "MỨC TƯ VẤN = CÓ ĐIỀU CHỈNH. Bạn được phép đề xuất mức KHÁC mức của mô hình, theo đúng trình tự: "
        "(1) gọi suggest_floor_adjustment để lấy MỨC NỀN; "
        "(2) gọi get_floor_context để lấy tín hiệu bối cảnh đã lượng hoá; "
        "(3) nếu được phép, gọi thêm các tool số liệu đơn vị thành viên (tồn kho · thu mua · tiêu thụ); "
        "(4) khi câu hỏi có SVR 3L hoặc giá nội địa, gọi get_private_price_benchmark để biết giá sàn nội "
        "địa SVR 3L đang thấp/trong/cao hơn vùng hợp lý theo giá mủ tư nhân. "
        "Mọi mức là của CHÍNH chủng loại được hỏi và cùng đơn vị của nó (FOB USD/tấn với chủng loại "
        "xuất khẩu): 'Mức mô hình' = muc_mo_hinh_de_xuat (KHÔNG phải gia_san_hien_hanh). CHỈ KHI hỏi giá "
        "NỘI ĐỊA SVR 3L: 'Mức mô hình' = muc_mo_hinh_noi_dia_uoc_tinh, "
        "'Điều chỉnh' = dieu_chinh_so_voi_mo_hinh (dieu_chinh_so_voi_mo_hinh_pct %), 'Mức đề xuất' = "
        "muc_de_xuat_noi_dia_svr3l — ghi ĐÚNG số tool trả (đã làm tròn theo bước ban hành 50.000 đồng) "
        "— và trích nguyên văn nội dung ket_luan làm căn cứ (tool đã so mức mô hình với vùng giá tư nhân và chọn "
        "điểm theo tồn kho — KHÔNG tự so lại). "
        "QUY TẮC ĐIỀU CHỈNH: chỉ dùng tín hiệu có trọng số 'bổ sung' (tồn kho; vùng giá tư nhân — chỉ "
        "cho SVR 3L nội địa) và số liệu đơn vị để lệch khỏi mức nền — tín hiệu trọng số 'mạnh' (4 futures "
        "+ giá mủ nước) ĐÃ nằm trong mô hình, cộng thêm lần nữa là tính hai lần; giá mủ chén không phải "
        "căn cứ. Mức đề xuất phải là bội của bước ban hành (5 USD/tấn FOB; 50.000 đồng/tấn nội địa). "
        "BẮT BUỘC trình bày theo các dòng: 'Mức mô hình: …' → 'Điều chỉnh: ±… (…%)' (phần BẠN lệch khỏi "
        "mức mô hình, 0 nếu giữ nguyên — KHÔNG phải chênh lệch so với giá hiện hành) → 'Mức đề xuất: …' "
        "→ 'So với giá sàn hiện hành: ±… (…%)' (Điều chỉnh = 0 thì lấy ĐÚNG chenh_so_voi_hien_hanh / "
        "chenh_so_voi_hien_hanh_pct của dòng đó trong suggest_floor_adjustment, không tự tính) → 'Căn cứ:' 2–4 gạch đầu dòng, mỗi gạch phải có "
        "SỐ THẬT từ tool. Hỏi chung không nêu chủng loại: trình bày các dòng trên cho SVR 10 / CSR 10 "
        "(mặt hàng chính), rồi 1–2 câu tóm các nhóm chủng loại còn lại kèm hành động và mức đề xuất. "
        "Biên độ điều chỉnh thông thường không quá ±2% so với mức mô hình (biên độ điều chỉnh trung "
        "bình mỗi lần ban hành trong lịch sử là 1,78%); nếu bạn thấy cần lệch nhiều hơn, phải nói rõ "
        "là bất thường và vì sao. Nếu bối cảnh không cho tín hiệu rõ, GIỮ NGUYÊN mức mô hình và nói ra."
    ),
}

#: Phương án giá sàn NHÁP trong phiên — người dùng nhờ Trợ lý lập/chỉnh số rồi sửa tiếp trên bảng.
#: Áp cho MỌI mức tư vấn: người dùng tự yêu cầu chỉnh là quyết định của người dùng, không phải
#: khuyến nghị của Trợ lý (mức "Theo mô hình" vẫn cấm Trợ lý TỰ đưa ra mức khác mô hình).
_PROPOSAL_RULES = (
    "PHƯƠNG ÁN NHÁP: người dùng có thể nhờ bạn lập/chỉnh một PHƯƠNG ÁN GIÁ SÀN NHÁP trong phiên "
    "(hiện trên bảng cạnh khung chat, không ghi vào biểu giá sàn). CHỈ gọi create_floor_proposal / "
    "adjust_floor_proposal khi NGƯỜI DÙNG yêu cầu rõ (lập phương án/bản nháp/tờ trình; tăng, giảm, "
    "đặt mức, đưa về mô hình, giữ như lần trước, hoàn tác) — không tự ý chỉnh, kể cả khi bạn thấy nên "
    "chỉnh. Người dùng bảo tăng/giảm/đặt giá sàn, kể cả nói trống ('tăng lên tí xíu giúp anh'), thì "
    "hiểu là chỉnh PHƯƠNG ÁN NHÁP và LÀM NGAY trong lượt đó, KHÔNG hỏi lại để xác nhận — bạn không "
    "sửa được giá chính thức nên không có rủi ro; làm xong nói rõ là đã chỉnh trên bản nháp. Mọi phép tính do công cụ làm, bạn KHÔNG tự cộng trừ hay làm tròn: 'tí xíu/chút/nhẹ/một "
    "ít' = step ±1; 'vài bước/kha khá' = step ±2 và nói rõ đã hiểu là 2 bước; 'X%' = percent; 'X USD' "
    "= amount field fob, 'X đồng' = amount field vnd; 'lên X/bằng X' = set; 'như mô hình' = "
    "reset_model; 'giữ như lần trước' = reset_current; 'bỏ lần vừa rồi' = undo. Không nêu chủng loại "
    "thì lấy chủng loại đang bàn ở lượt trước; không có thì áp cho mọi chủng loại (grades ['all']) "
    "và nói rõ đã áp cho tất cả. Giá nội địa của dòng có FOB tự tính theo FOB — chỉ dùng field vnd "
    "khi người dùng nói rõ giá nội địa/đồng. Chưa có phương án mà người dùng bảo tăng/giảm: đang nói về "
    "giá hiện hành thì base current, đang nói về mức mô hình gợi ý thì base model. Sau khi chỉnh: chép "
    "nguyên mô tả trong da_lam (giữ dạng 'số cũ → số mới'), nói rõ xuất phát từ đâu nếu vừa lập "
    "phương án (moi_lap_phuong_an), nêu canh_bao nếu có, nhắc ngắn đây là bản nháp trong phiên (sửa tiếp trên bảng, xem trước tờ trình "
    "hoặc lưu bản nháp). Không bình luận nên hay không chỉnh trừ khi được hỏi. Hỏi số của phương án "
    "thì đọc khối PHƯƠNG ÁN GIÁ SÀN NHÁP ĐANG MỞ (nếu có), không gọi lại công cụ; giá chính thức vẫn "
    "là giá của lần ban hành, đừng lẫn với số của phương án. Người dùng bảo 'đưa vào bảng/phương "
    "án', 'lập bảng' thì PHẢI gọi công cụ: đưa mức bạn vừa đề xuất vào phương án = "
    "adjust_floor_proposal op set đúng mức đề xuất cho từng chủng loại đó (chưa có phương án thì "
    "công cụ tự lập); mức đề xuất trùng mức mô hình mà chưa có phương án thì gọi "
    "create_floor_proposal. CHỈ nói 'đã lập/đã chỉnh/bản nháp trong phiên' khi công cụ vừa chạy "
    "THÀNH CÔNG trong lượt này; kết quả có error thì nói rõ CHƯA đổi gì và lý do."
)

SYSTEM = (
    "Bạn là Trợ lý phân tích thị trường cao su của Tập đoàn Công nghiệp Cao su Việt Nam (VRG). "
    "Trả lời NGẮN GỌN, chuyên nghiệp, bằng tiếng Việt; xưng 'em', gọi người dùng 'anh/chị'. "
    "TUYỆT ĐỐI KHÔNG bịa số liệu: mọi con số/giá/xu hướng phải lấy từ KẾT QUẢ TOOL — nếu chưa có "
    "dữ liệu thì gọi tool phù hợp; nếu tool báo không có dữ liệu thì nói rõ 'chưa có số liệu', "
    "không tự suy đoán con số. KHÔNG lấy số liệu ngày khác đắp cho ngày được hỏi. "
    "Giá ghi 'No Trading' là phiên sàn không giao dịch, KHÔNG phải giá bằng 0. "
    "Luôn nêu ĐƠN VỊ TÍNH đúng như tool trả về (USD/tấn · VNĐ/tấn · đồng/độ · tấn) và KHÔNG tự quy đổi. "
    "Viết số kiểu Việt Nam: dấu chấm ngăn nghìn, dấu phẩy thập phân (2.340 USD/tấn; +0,6%); tool có "
    "câu tóm tắt đã định dạng sẵn (tom_tat, ket_luan…) thì CHÉP NGUYÊN số trong đó, đừng tự định dạng lại. "
    "KHÔNG ghi tên trường kỹ thuật (ket_luan, don_vi, tom_tat…) trong câu trả lời. "
    "Khi hỏi diễn biến/xu hướng → gọi tool chuỗi giá; hỏi giá hiện tại → tool ảnh chụp. "
    "Bạn CHỈ ĐỌC dữ liệu: mọi nhận định/khuyến nghị chỉ hiển thị để tham khảo, KHÔNG ghi vào biểu "
    "giá sàn và không làm thay đổi bất kỳ số liệu nào của hệ thống (phương án nháp trong phiên — "
    "xem dưới — cũng KHÔNG ghi vào hệ thống). "
    + _REASONING + " " + _FACTOR_RANKING + " " + _PROPOSAL_RULES + " "
    "Mọi khuyến nghị giá sàn đều là GỢI Ý tham khảo — quyết định cuối thuộc về Ban lãnh đạo. "
    "Khi tool trả bảng/biểu đồ, hệ thống TỰ hiển thị cho người dùng — bạn chỉ diễn giải ý nghĩa, "
    "không liệt kê lại toàn bộ số trong bảng. Nêu rõ kỳ dữ liệu (ngày/tuần) khi trả lời."
)


def system_prompt(advice: str) -> str:
    """Prompt hệ thống + luật của MỨC TƯ VẤN đang chọn + ngày hôm nay.

    Ngày tính MỖI lượt hỏi: trước đây nằm trong hằng số tính lúc nạp module nên máy chủ chạy qua
    đêm là Trợ lý nói sai ngày (nhật ký prod 15/09/2026: "Hôm nay, 14/09").
    """
    return (SYSTEM + " " + _ADVICE_RULES.get(advice, _ADVICE_RULES[DEFAULT_ADVICE])
            + f" Hôm nay là {edit_window.today().isoformat()}.")


def enabled_packs() -> list[str] | None:
    """Gói admin bật ở Cấu hình hệ thống (CSV). Chưa đặt → None = bật tất cả.

    Đã đặt nhưng gõ sai hết (vd "iternal") → trả `[]` chứ KHÔNG phải None: admin có ý định giới
    hạn, gõ nhầm mà lại bật thêm gói cho mọi người là đảo ngược ý định (fail open).
    """
    raw = (config_repo.get_value(CONFIG_KEY, "") or "").strip()
    if not raw:
        return None
    return [k.strip() for k in raw.split(",") if k.strip() in assistant_tools.PACKS]


def _scope(caps: dict[str, str] | None, packs: list[str] | None) -> list[str] | None:
    """Giao giữa gói admin bật và gói người dùng chọn trong phiên chat."""
    admin = enabled_packs()
    if packs is None:
        return admin
    chosen = [p for p in packs if p in assistant_tools.PACKS]
    return [p for p in chosen if admin is None or p in admin]


def packs_for(caps: dict[str, str] | None) -> list[dict[str, Any]]:
    """Mô tả gói cho frontend (chip chọn nhóm dữ liệu)."""
    return assistant_tools.pack_summary(caps, enabled_packs())


def _parse_args(raw: str | None) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _dedup(items: list[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _log_turn(session_id: str | None, username: str | None, messages: list[dict[str, str]],
              answer: str, tools: list[str], sources: list[str], packs: list[str] | None,
              advice: str, model: str, started: float) -> None:
    """Ghi 1 lượt vào nhật ký hỏi–đáp. Log hỏng KHÔNG được làm hỏng câu trả lời của người dùng."""
    if not session_id or not username:
        return
    try:
        from app.services import assistant_log_repo  # nạp muộn: nhật ký là tính năng phụ trợ
        question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        assistant_log_repo.log_turn(
            session_id=session_id, username=username, question=question, answer=answer,
            tools=tools, sources=sources, packs=packs, advice=advice, model=model,
            latency_ms=int((time.time() - started) * 1000))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Không ghi được nhật ký Trợ lý AI: %s", exc)


def _session_proposal(raw: dict | None) -> dict | None:
    """Phương án nháp frontend gửi kèm — hỏng thì bỏ qua (chat vẫn phải chạy), không làm lỗi lượt hỏi."""
    try:
        return floor_proposal.sanitize(raw)
    except (floor_proposal.ProposalError, TypeError, ValueError, AttributeError, KeyError) as exc:
        logger.warning("Bỏ qua phương án nháp không hợp lệ: %s", exc)
        return None


def chat(messages: list[dict[str, str]], caps: dict[str, str] | None = None,
         packs: list[str] | None = None, advice: str = DEFAULT_ADVICE,
         session_id: str | None = None, username: str | None = None,
         proposal: dict | None = None) -> dict[str, Any]:
    """Chạy 1 lượt hỏi–đáp (kèm lịch sử). Trả {answer, artifacts, sources, proposal}.

    `proposal` = phương án giá sàn nháp của phiên (frontend giữ). Trả `proposal` khác None khi lượt
    này đã lập/chỉnh phương án ⇒ frontend thay bằng bản mới.
    """
    provider = (config_repo.get_value("LLM_PROVIDER", "openai") or "openai").lower()
    if provider != "openai":
        raise llm.LLMNotConfigured(
            "Trợ lý AI hiện chỉ hỗ trợ OpenAI (cần function-calling). "
            "Vào Quản trị → Cấu hình hệ thống → tab AI, đặt LLM_PROVIDER=openai."
        )
    client, model = llm.openai_client()
    advice = advice if advice in ADVICE_MODES else DEFAULT_ADVICE
    scope = _scope(caps, packs)
    started = time.time()
    ctx: dict[str, Any] = {"proposal": _session_proposal(proposal), "advice": advice, "changed": False}
    convo: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(advice)}]
    if ctx["proposal"]:
        convo.append({"role": "system", "content": proposal_tools.context_block(ctx["proposal"], advice)})
    convo += [{"role": m["role"], "content": m["content"]} for m in messages
              if m.get("role") in ("user", "assistant") and m.get("content")]
    tools = assistant_tools.openai_tools(caps, scope)
    if advice == "data":
        tools = [t for t in tools if t["function"]["name"] not in _ADVICE_TOOLS]
    artifacts: list[dict] = []
    sources: list[str] = []
    used: list[str] = []
    question = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    retried = False

    force = False   # lượt làm lại của hàng rào: chỉ 2 công cụ phương án, bắt buộc gọi
    for _ in range(MAX_ITERS):
        resp = client.chat.completions.create(
            model=model, messages=convo,
            tools=[t for t in tools if t["function"]["name"] in claim_guard.PROPOSAL_TOOLS] if force else tools,
            tool_choice="required" if force else "auto",
            max_completion_tokens=1500,
        )
        force = False
        msg = resp.choices[0].message
        if not msg.tool_calls:
            answer = (msg.content or "").strip()
            # Nói "đã chỉnh bản nháp" mà lượt này không có thay đổi thật ⇒ bắt làm lại một lần, vẫn sai
            # thì đính chính — xem assistant_claim_guard.
            if not retried and claim_guard.needs_retry(question, answer, ctx["changed"]):
                retried = force = True
                logger.info("Trợ lý chưa chỉnh phương án dù được yêu cầu / báo sai — bắt gọi công cụ")
                convo.append({"role": "assistant", "content": answer})
                convo.append({"role": "system", "content": claim_guard.RETRY_MESSAGE})
                continue
            if claim_guard.false_claim(question, answer, ctx["changed"]):
                answer += claim_guard.CORRECTION
            _log_turn(session_id, username, messages, answer, used, _dedup(sources),
                      scope, advice, model, started)
            return {"answer": answer, "artifacts": artifacts, "sources": _dedup(sources),
                    "proposal": ctx["proposal"] if ctx["changed"] else None}
        # Ghi lại lượt assistant kèm tool_calls rồi thực thi từng tool.
        convo.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            used.append(tc.function.name)
            if advice == "data" and tc.function.name in _ADVICE_TOOLS:
                res = {"summary": {"error": "Chế độ 'Chỉ tra số' không dùng công cụ khuyến nghị. "
                                            "Hãy trả lời bằng số liệu và mời người dùng chuyển mức tư vấn."}}
            else:
                res = assistant_tools.run_tool(tc.function.name, _parse_args(tc.function.arguments),
                                               caps, scope, ctx)
                if advice == "model" and tc.function.name in _MODEL_MODE_FILTERS:
                    res = _MODEL_MODE_FILTERS[tc.function.name](res)
            if res.get("artifact"):
                artifacts.append(res["artifact"])
            if res.get("source"):
                sources.append(res["source"])
            convo.append({"role": "tool", "tool_call_id": tc.id,
                          "content": json.dumps(res.get("summary", {}), ensure_ascii=False, default=str)})

    answer = "Câu hỏi cần quá nhiều bước tra cứu — anh/chị vui lòng hỏi cụ thể hơn giúp em."
    _log_turn(session_id, username, messages, answer, used, _dedup(sources), scope, advice,
              model, started)
    return {"answer": answer, "artifacts": artifacts, "sources": _dedup(sources),
            "proposal": ctx["proposal"] if ctx["changed"] else None}
