const BRAND = { green: "#13A05A", navy: "#0E1B2C" };

export default function App() {
  return (
    <main style={{ fontFamily: "Arial, sans-serif", color: BRAND.navy, padding: 48 }}>
      <h1 style={{ color: BRAND.green, marginBottom: 8 }}>VRG · AI Dự báo Giá Cao su</h1>
      <p style={{ opacity: 0.8 }}>Executive Command Center — scaffold.</p>
      <ul style={{ lineHeight: 1.8 }}>
        <li>Dashboard giám sát thị trường đa sàn</li>
        <li>Dự báo giá (Bull / Base / Bear)</li>
        <li>RAG Chatbot + cảnh báo đa kênh</li>
      </ul>
    </main>
  );
}
