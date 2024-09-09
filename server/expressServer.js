import express, {Router} from "express"
import { authMiddleware } from "./middleware/auth.js"
import spokenDataRoutes from "./routes/spokenData.js"
import morgan from "morgan"

const app = express()

const baseLevelRouter = Router()

const apiRouter = Router()

apiRouter.use(express.json())
apiRouter.use(authMiddleware)
apiRouter.use("/spokenData", spokenDataRoutes)

baseLevelRouter.use("/api", apiRouter)

app.use(baseLevelRouter)
app.use(morgan())

export default app