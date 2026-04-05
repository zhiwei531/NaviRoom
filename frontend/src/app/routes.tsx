import { createBrowserRouter } from "react-router";
import { HomePage } from "./pages/HomePage";
import { UploadPage } from "./pages/UploadPage";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: HomePage,
  },
  {
    path: "/upload",
    Component: UploadPage,
  },
]);
