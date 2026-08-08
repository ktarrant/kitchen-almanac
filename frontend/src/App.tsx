const stages = [
  "Choose crops",
  "Select varieties",
  "Build grow guides",
  "Plan the garden",
  "Forecast the harvest",
  "Use what you grow"
];

export default function App() {
  return (
    <main>
      <p className="eyebrow">Kitchen Almanac</p>
      <h1>Plan a garden around the food you want to eat.</h1>
      <p className="intro">
        Turn a vegetable wishlist into a local planting calendar, a practical
        layout, and a realistic harvest forecast.
      </p>
      <ol>
        {stages.map((stage, index) => (
          <li key={stage}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {stage}
          </li>
        ))}
      </ol>
      <p className="status">Foundation and seed catalog in progress.</p>
    </main>
  );
}
