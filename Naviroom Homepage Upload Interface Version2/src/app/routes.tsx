import { createBrowserRouter } from "react-router";
import { HomePage } from "./pages/HomePage";
import { UploadPage } from "./pages/UploadPage";
import { TutorialPage } from "./pages/TutorialPage";
import { AboutPage } from "./pages/AboutPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: HomePage,
  },
  {
    path: "/upload",
    Component: UploadPage,
  },
  {
    path: "/tutorial",
    Component: TutorialPage,
  },
  {
    path: "/about",
    Component: AboutPage,
  },
]);
