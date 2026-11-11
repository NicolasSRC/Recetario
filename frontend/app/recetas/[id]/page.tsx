import { RecipeBook } from "@/components/RecipeBook";

export default async function RecipePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RecipeBook key={id} recipeId={id} />;
}
