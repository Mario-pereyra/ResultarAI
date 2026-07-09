type HomeContentProps = {
  title: string;
  greeting: string;
};

/**
 * Componente presentacional trivial, sin dependencias de servidor.
 * Separado de `page.tsx` (Server Component) para poder testearlo con
 * @testing-library/react + Vitest sin depender del runtime de next-intl.
 */
export function HomeContent({ title, greeting }: HomeContentProps) {
  return (
    <main>
      <h1>{title}</h1>
      <p>{greeting}</p>
    </main>
  );
}
