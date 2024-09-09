import mongoose from "mongoose"

const SpokenDataDocSchema = new mongoose.Schema({
  speaker: { type: String, required: true },
  text: { type: String, required: true },
  date: { type: Date, default: Date.now },
  embedding: { type: [Number], required: true } // Array of numbers for the vector
});

export const SpokenDataDocModel = mongoose.model("SpokenDataDoc", SpokenDataDocSchema)