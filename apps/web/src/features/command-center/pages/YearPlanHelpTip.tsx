/* Biểu tượng ⓘ nhỏ cạnh nhãn: giải thích hiện khi rê chuột / focus bàn phím — thay cho đoạn chữ dài đầu màn. */

import { InfoCircleOutlined } from "@ant-design/icons";
import { Tooltip } from "antd";

export default function YearPlanHelpTip({ text }: { text: string }) {
  return (
    <Tooltip title={text} placement="right" mouseEnterDelay={0.15}>
      <InfoCircleOutlined className="yp-help" tabIndex={0} role="img" aria-label={text} />
    </Tooltip>
  );
}
