import { redirect } from "next/navigation";

/** The product is the application, not a marketing page. */
export default function Home() {
  redirect("/dashboard");
}
