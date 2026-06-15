import { footer } from "../../data/sample-data-panels";

export default function Footer() {
  return (
    <footer className="footer">
      <div>{footer.left}</div>
      <div>{footer.right}</div>
    </footer>
  );
}
