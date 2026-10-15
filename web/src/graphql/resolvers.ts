// Hand-written until codegen (make codegen) generates resolver types into src/generated.
export interface Health {
  status: string;
  service: string;
  version: string;
}

export const resolvers = {
  Query: {
    health: (): Health => ({ status: "ok", service: "aml-web", version: "0.0.0" }),
  },
};
