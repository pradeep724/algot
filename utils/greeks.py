import math
from scipy.stats import norm

class GreeksCalculator:
    @staticmethod
    def d1(S, K, T, r, sigma):
        return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

    @staticmethod
    def d2(S, K, T, r, sigma):
        return GreeksCalculator.d1(S, K, T, r, sigma) - sigma * math.sqrt(T)

    @staticmethod
    def calculate_greeks(S, K, T, r, sigma, option_type):
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        d2 = GreeksCalculator.d2(S, K, T, r, sigma)

        if option_type == 'CE':
            delta = norm.cdf(d1)
            theta = (- (S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
            vega = S * norm.pdf(d1) * math.sqrt(T) / 100
        else:  # PE
            delta = -norm.cdf(-d1)
            theta = (- (S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
            vega = S * norm.pdf(d1) * math.sqrt(T) / 100

        gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
        rho = K * T * math.exp(-r * T) * (norm.cdf(d2) if option_type == 'CE' else norm.cdf(-d2)) / 100

        return {
            'delta': delta,
            'theta': theta,
            'vega': vega,
            'gamma': gamma,
            'rho': rho
        }
