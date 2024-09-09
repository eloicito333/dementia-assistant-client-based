import {config} from "../config.js"

export const authMiddleware = (req, res, next) => {
  console.log(req.headers)
  if (req.headers?.authorization === config.DANGEROUSLY_SET_AUTHENTICATION_STRING) return next()
  
  res.status(401).json({error: {message: "Failed authentication"}})
}