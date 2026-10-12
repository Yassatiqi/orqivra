export class OrqivraError extends Error {
  readonly exitCode: number;

  constructor(message: string, exitCode = 2) {
    super(message);
    this.name = 'OrqivraError';
    this.exitCode = exitCode;
  }
}

export class ConcurrentUpdateError extends OrqivraError {
  constructor(message: string) {
    super(message, 3);
    this.name = 'ConcurrentUpdateError';
  }
}

export class UnsafePathError extends OrqivraError {
  constructor(message: string) {
    super(message, 4);
    this.name = 'UnsafePathError';
  }
}

export class InputOutputError extends OrqivraError {
  constructor(message: string) {
    super(message, 4);
    this.name = 'InputOutputError';
  }
}
