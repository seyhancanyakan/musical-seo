import type { NextPageContext } from "next";

// Next.js her zaman derleme sirasinda pages/_error tabanli /404 ve /500
// sayfalarini uretir (App Router'da bile). Ustteki dahili sablon 15.x'te
// bilinen bir hata veriyor: "<Html> should not be imported outside of
// pages/_document". Bu minimal ozel _error, o hatali dahili bileseni
// gecersiz kilar ve derleme hatasini ortadan kaldirir.
function CustomError({ statusCode }: { statusCode?: number }) {
  return (
    <main
      style={{
        minHeight: "60vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: 32,
        textAlign: "center",
      }}
    >
      <h1 className="nb-h" style={{ fontSize: 48 }}>
        {statusCode ?? "Hata"}
      </h1>
      <p>Bir sorun olustu.</p>
      <a href="/" className="nb-btn">
        Ana sayfaya don
      </a>
    </main>
  );
}

CustomError.getInitialProps = ({ res, err }: NextPageContext) => {
  const statusCode = res ? res.statusCode : err ? err.statusCode : 404;
  return { statusCode };
};

export default CustomError;
